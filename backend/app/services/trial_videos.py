import asyncio
import hashlib
import logging
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile
from jose import JWTError, jwt
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.group import Group
from app.models.trial_video import TrialVideo
from app.models.user import User, UserRole


SUBJECTS = ("语文", "数学", "英语", "物理", "政治", "道德与法治", "化学", "生物", "地理", "历史")
EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".flv", ".wmv"}
mutation_lock = asyncio.Lock()
analysis_lock = asyncio.Lock()
cover_lock = asyncio.Lock()
logger = logging.getLogger(__name__)
DEFAULT_COVER = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360">
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#164e63"/><stop offset="1" stop-color="#0f172a"/></linearGradient></defs>
<path fill="url(#bg)" d="M0 0h640v360H0z"/><rect x="90" y="55" width="460" height="250" rx="16" fill="#155e75" stroke="#67e8f9" stroke-opacity=".4"/>
<path d="M140 110h180m-180 35h120m-120 35h90" stroke="#cffafe" stroke-width="8" stroke-linecap="round" opacity=".5"/>
<circle cx="420" cy="146" r="30" fill="#a5f3fc"/><path d="M365 265v-46a55 55 0 0 1 110 0v46" fill="#22d3ee"/>
<path d="M300 285h205" stroke="#cffafe" stroke-width="10" stroke-linecap="round"/></svg>'''


def extract_cover_with_opencv(path: Path, cover: Path) -> bool:
    try:
        import cv2
        capture = cv2.VideoCapture(str(path))
        try:
            capture.set(cv2.CAP_PROP_POS_MSEC, 1000)
            ok, frame = capture.read()
            if not ok:
                capture.set(cv2.CAP_PROP_POS_MSEC, 0)
                ok, frame = capture.read()
            if not ok or frame is None:
                return False
            height, width = frame.shape[:2]
            frame = cv2.resize(frame, (640, max(1, round(height * 640 / width))))
            ok, encoded = cv2.imencode(".jpg", frame)
            if ok:
                cover.write_bytes(encoded.tobytes())
            return bool(ok)
        finally:
            capture.release()
    except Exception as error:
        logger.debug("OpenCV cover extraction unavailable: %s", error)
        return False


async def ensure_cover(video: TrialVideo) -> Path | None:
    path = file_path(video)
    cover = path.with_suffix(".cover.jpg")
    if cover.is_file():
        return cover
    async with cover_lock:
        if cover.is_file():
            return cover
        try:
            # 从前 30 帧中选代表画面，兼容已有视频，无需数据库迁移。
            result = await asyncio.to_thread(subprocess.run, [
                "ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf",
                "thumbnail=30,scale=640:-2", "-frames:v", "1", str(cover),
            ], capture_output=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode == 0 and cover.is_file() and cover.stat().st_size:
                return cover
        except (OSError, subprocess.TimeoutExpired):
            logger.info("Video cover unavailable: %s", video.id)
        if await asyncio.to_thread(extract_cover_with_opencv, path, cover):
            return cover
        cover.unlink(missing_ok=True)
        return None


def now() -> datetime:
    return datetime.utcnow()


def storage_root() -> Path:
    root = Path(settings.TRIAL_VIDEO_STORAGE_DIR).resolve()
    if root.is_relative_to(Path(settings.UPLOAD_DIR).resolve()):
        raise RuntimeError("试讲视频必须存放在公共 uploads 目录之外")
    root.mkdir(parents=True, exist_ok=True)
    return root


def file_path(video: TrialVideo) -> Path:
    if not video.file_name or Path(video.file_name).name != video.file_name:
        raise HTTPException(410, "原视频已删除或到期清理")
    return storage_root() / video.file_name


def available(video: TrialVideo) -> bool:
    return bool(video.file_name and video.file_status == "available" and (
        video.expires_at is None or video.expires_at > now()))


async def is_mentor(db: AsyncSession, video: TrialVideo, user: User) -> bool:
    if user.role != UserRole.INSTRUCTOR or video.semester_id is None:
        return False
    return bool(await db.scalar(select(Group.id).where(
        Group.semester_id == video.semester_id,
        Group.student_id == video.owner_id,
        Group.instructor_id == user.id)))


async def can_manage_private(db: AsyncSession, video: TrialVideo, user: User) -> bool:
    return user.role == UserRole.ADMIN or video.owner_id == user.id or await is_mentor(db, video, user)


async def ensure_can_play(db: AsyncSession, video: TrialVideo, user: User) -> None:
    if not available(video):
        raise HTTPException(410, "原视频已删除或超过15天保留期")
    if video.is_public and video.blocked_at is None:
        return
    if not await can_manage_private(db, video, user):
        raise HTTPException(403, "无权观看该私密视频")


def validate_public(title: str, subject: str) -> None:
    if not title.strip():
        raise HTTPException(422, "公开视频必须填写标题")
    if subject not in SUBJECTS:
        raise HTTPException(422, "请选择有效学科")


async def used_bytes(db: AsyncSession, owner_id: int = None) -> int:
    query = select(func.coalesce(func.sum(TrialVideo.file_size), 0)).where(TrialVideo.file_name.is_not(None))
    if owner_id is not None:
        query = query.where(TrialVideo.owner_id == owner_id, TrialVideo.source == "student")
    return int(await db.scalar(query) or 0)


async def remove_file(video: TrialVideo, status: str) -> None:
    if video.file_name:
        path = file_path(video)
        await asyncio.to_thread(path.unlink, missing_ok=True)
        await asyncio.to_thread(path.with_suffix(".cover.jpg").unlink, missing_ok=True)
    video.file_name = None
    video.file_size = 0
    video.file_status = status
    video.is_public = False
    video.expires_at = None


async def cleanup_expired(db: AsyncSession) -> int:
    rows = (await db.scalars(select(TrialVideo).where(
        TrialVideo.file_name.is_not(None), TrialVideo.expires_at <= now()))).all()
    for video in rows:
        await remove_file(video, "expired")
    await db.flush()
    return len(rows)


async def save_upload(db: AsyncSession, upload: UploadFile, owner: User, source: str) -> tuple:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in EXTENSIONS:
        raise HTTPException(422, "不支持的视频格式，请优先上传 MP4 或 WebM")
    root = storage_root()
    total_remaining = settings.TRIAL_VIDEO_TOTAL_BYTES - await used_bytes(db)
    owner_remaining = settings.TRIAL_VIDEO_USER_BYTES - await used_bytes(db, owner.id)
    limit = min(settings.TRIAL_VIDEO_MAX_BYTES, total_remaining,
                owner_remaining if source == "student" else settings.TRIAL_VIDEO_MAX_BYTES)
    if limit <= 0:
        raise HTTPException(413, "视频容量额度已用完，请先清理视频")
    if upload.size is not None and upload.size > limit:
        raise HTTPException(413, "视频超过单文件、个人或全站容量上限")
    name = uuid.uuid4().hex + extension
    path = root / name
    size = 0
    digest = hashlib.sha256()
    try:
        async with aiofiles.open(path, "wb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, "视频超过单文件、个人或全站容量上限")
                if shutil.disk_usage(root).free < settings.TRIAL_VIDEO_MIN_FREE_BYTES + len(chunk):
                    raise HTTPException(507, "服务器剩余空间不足，请联系管理员清理")
                digest.update(chunk)
                await target.write(chunk)
        if not size:
            raise HTTPException(422, "不能上传空视频")
        return name, size, digest.hexdigest()
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def public_data(video: TrialVideo, author: str, college: str | None = None, viewer_id: int | None = None) -> dict:
    return dict(id=video.id, title=video.title, subject=video.subject,
                description=video.description, author=author, college=college or "",
                can_delete=video.source == "student" and video.owner_id == viewer_id,
                presenter_type=video.presenter_type, source=video.source,
                created_at=video.created_at, published_at=video.published_at)


def management_data(video: TrialVideo, author: str, college: str | None = None, viewer_id: int | None = None) -> dict:
    return dict(public_data(video, author, college, viewer_id), is_public=video.is_public,
                semester_id=video.semester_id, original_name=video.original_name,
                file_size=video.file_size, file_status=video.file_status,
                available=available(video), expires_at=video.expires_at,
                blocked=video.blocked_at is not None, moderation_reason=video.moderation_reason,
                analysis_status=video.analysis_status)


def ticket_key() -> str:
    return hashlib.sha256((settings.JWT_SECRET_KEY + ":trial-video-playback").encode()).hexdigest()


def create_ticket(video_id: int, user_id: int) -> str:
    return jwt.encode(dict(video_id=video_id, viewer=user_id, exp=now() + timedelta(hours=1)),
                      ticket_key(), algorithm=settings.JWT_ALGORITHM)


def ticket_viewer(ticket: str, video_id: int) -> int:
    try:
        payload = jwt.decode(ticket, ticket_key(), algorithms=[settings.JWT_ALGORITHM])
        if payload.get("video_id") != video_id:
            raise ValueError()
        return int(payload["viewer"])
    except (JWTError, ValueError, TypeError, KeyError):
        raise HTTPException(401, "播放凭据无效或已过期，请重新打开视频")


def byte_range(header: str, size: int) -> tuple:
    if header is None:
        return 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not match or not any(match.groups()):
        raise HTTPException(416, headers={"Content-Range": f"bytes */{size}"})
    start_text, end_text = match.groups()
    if start_text:
        start = int(start_text)
        end = min(int(end_text), size - 1) if end_text else size - 1
    else:
        start, end = max(0, size - int(end_text)), size - 1
    if start > end or start >= size:
        raise HTTPException(416, headers={"Content-Range": f"bytes */{size}"})
    return start, end, 206


async def stream_chunks(path: Path, start: int, end: int):
    async with aiofiles.open(path, "rb") as source:
        await source.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = await source.read(min(256 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


async def analyze_video(video_id: int) -> None:
    async with analysis_lock:
        await run_analysis(video_id)


async def run_analysis(video_id: int) -> None:
    async with async_session_factory() as db:
        video = await db.get(TrialVideo, video_id)
        if video is None:
            return
        if not available(video):
            video.analysis_status = "failed"
            video.analysis_error = "原视频已删除或到期，无法完成分析"
            await db.commit()
            return
        try:
            from app.services.video_analysis_service import get_video_analysis_service
            result = await get_video_analysis_service().analyze_video(str(file_path(video)))
            video.analysis_result = result
            video.analysis_status = "completed"
            video.analysis_error = ""
        except Exception:
            logger.exception("Trial video analysis failed: %s", video_id)
            video.analysis_status = "failed"
            video.analysis_error = "视频分析暂时失败，视频已保存，可在我的视频中查看"
        await db.commit()


async def recover_interrupted_analysis() -> None:
    async with async_session_factory() as db:
        await db.execute(update(TrialVideo).where(TrialVideo.analysis_status == "processing").values(
            analysis_status="failed", analysis_error="分析因服务重启中断，已保存的视频仍可正常观看"))
        await db.commit()


async def maintenance() -> None:
    while True:
        try:
            async with mutation_lock:
                async with async_session_factory() as db:
                    await cleanup_expired(db)
                    await db.commit()
        except Exception:
            logger.exception("Trial video expiry cleanup failed")
        await asyncio.sleep(3600)
