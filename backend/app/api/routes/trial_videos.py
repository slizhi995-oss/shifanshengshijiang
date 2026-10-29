import mimetypes
from datetime import timedelta
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_student
from app.models.group import Group
from app.models.semester import Semester, SemesterStatus
from app.models.trial_video import TrialVideo, TrialVideoBlock, TrialVideoComment
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.services import trial_videos as service


router = APIRouter()


class VideoUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    subject: Optional[str] = Field(None, max_length=32)
    description: Optional[str] = Field(None, max_length=2000)
    presenter_name: Optional[str] = Field(None, max_length=64)
    presenter_type: Optional[Literal["student", "teacher"]] = None
    is_public: Optional[bool] = None


class Takedown(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class CommentCreate(BaseModel):
    model_config = {"extra": "forbid"}
    content: str = Field(min_length=1, max_length=1000)
    parent_id: Optional[int] = Field(None, gt=0)

    @field_validator("content")
    @classmethod
    def nonempty_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请输入评论内容")
        return value


async def get_video(db: AsyncSession, identifier: int) -> TrialVideo:
    video = await db.get(TrialVideo, identifier)
    if video is None:
        raise HTTPException(404, "视频不存在")
    return video


async def author_name(db: AsyncSession, video: TrialVideo) -> str:
    if video.source == "example":
        return video.presenter_name
    return await db.scalar(select(User.name).where(User.id == video.owner_id)) or ""


@router.get("/upload-options")
async def upload_options(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(select(Semester.id, Semester.name, User.name.label("instructor_name"))
        .outerjoin(Group, and_(Group.semester_id == Semester.id, Group.student_id == user.id))
        .outerjoin(User, User.id == Group.instructor_id)
        .where(or_(Group.id.is_not(None), Semester.status == SemesterStatus.ACTIVE))
        .order_by(Semester.created_at.desc()))).all()
    return dict(subjects=service.SUBJECTS, semesters=[dict(row._mapping) for row in rows],
                max_bytes=settings.TRIAL_VIDEO_MAX_BYTES, user_max_bytes=settings.TRIAL_VIDEO_USER_BYTES,
                used_bytes=await service.used_bytes(db, user.id), private_days=settings.TRIAL_VIDEO_PRIVATE_DAYS)


@router.post("/upload", status_code=201)
async def upload_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    source: Literal["student", "example"] = Form("student"),
    title: str = Form("", max_length=200),
    subject: str = Form("", max_length=32),
    description: str = Form("", max_length=2000),
    is_public: bool = Form(True),
    semester_id: Optional[int] = Form(None),
    presenter_name: str = Form("", max_length=64),
    presenter_type: Literal["student", "teacher"] = Form("student"),
    analysis_task_id: Optional[str] = Form(None, max_length=64),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if source == "example" and user.role != UserRole.ADMIN:
        raise HTTPException(403, "只有管理员可以上传优秀示例")
    if source == "student" and user.role != UserRole.STUDENT:
        raise HTTPException(403, "只有学生可以上传同学试讲")
    if source == "example":
        is_public = True
        semester_id = None
        if not presenter_name.strip():
            raise HTTPException(422, "请填写讲授者姓名")
    if is_public:
        service.validate_public(title, subject)
    elif subject and subject not in service.SUBJECTS:
        raise HTTPException(422, "请选择有效学科")
    if source == "student":
        options = await upload_options(db, user)
        choices = options["semesters"]
        if semester_id is None:
            # 优先关联学生已分组的最新进行中批次，随后是历史分组、进行中批次。
            semester_id = await db.scalar(select(Semester.id)
                .join(Group, and_(Group.semester_id == Semester.id, Group.student_id == user.id))
                .order_by((Semester.status == SemesterStatus.ACTIVE).desc(),
                          Semester.created_at.desc(), Semester.id.desc()).limit(1))
            if semester_id is None:
                semester_id = await db.scalar(select(Semester.id)
                    .where(Semester.status == SemesterStatus.ACTIVE)
                    .order_by(Semester.created_at.desc(), Semester.id.desc()).limit(1))
        if semester_id is not None and semester_id not in {item["id"] for item in choices}:
            raise HTTPException(403, "无权关联该批次")
    original_name = Path((video.filename or "video.mp4").replace("\\", "/")).name[:255]
    async with service.mutation_lock:
        await service.cleanup_expired(db)
        await db.commit()
        name, size, digest = await service.save_upload(db, video, user, source)
        try:
            analysis = None
            if source == "student" and analysis_task_id:
                from app.api.routes.video_analysis import _standalone_analysis_results
                evaluated = _standalone_analysis_results.get(analysis_task_id)
                if not evaluated or evaluated.get("user_id") != user.id:
                    raise HTTPException(403, "评估任务不存在或不属于当前用户，请重新评估")
                if evaluated.get("status") != "completed" or not isinstance(evaluated.get("analysis"), dict):
                    raise HTTPException(422, "请等待 AI 评估完成后再上传")
                if evaluated.get("file_hash") != digest:
                    raise HTTPException(422, "当前视频与已评估视频不一致，请重新评估")
                analysis = evaluated["analysis"]
            block = await db.scalar(select(TrialVideoBlock).where(
                TrialVideoBlock.owner_id == user.id, TrialVideoBlock.sha256 == digest)) if source == "student" else None
            if block and is_public:
                raise HTTPException(403, "该视频已被管理员下架，不能重新公开")
            record = TrialVideo(
                owner_id=user.id, semester_id=semester_id, source=source,
                title=title.strip() or Path(original_name).stem[:200], subject=subject,
                description=description.strip(), presenter_name=presenter_name.strip() if source == "example" else "",
                presenter_type=presenter_type if source == "example" else "student",
                original_name=original_name, file_name=name, file_size=size, sha256=digest,
                is_public=is_public, published_at=service.now() if is_public else None,
                expires_at=None if is_public else service.now() + timedelta(days=settings.TRIAL_VIDEO_PRIVATE_DAYS),
                blocked_at=service.now() if block else None, moderation_reason=block.reason if block else "",
                analysis_status=("completed" if analysis is not None else "processing") if source == "student" else "not_required",
                analysis_result=analysis)
            db.add(record)
            await db.commit()
            await db.refresh(record)
        except BaseException:
            (service.storage_root() / name).unlink(missing_ok=True)
            raise
    if source == "student" and record.analysis_status == "processing":
        background_tasks.add_task(service.analyze_video, record.id)
    return service.management_data(record, user.name if source == "student" else record.presenter_name,
                                   user.college, user.id)


async def list_rows(db: AsyncSession, query, page: int, page_size: int, private: bool, user: User) -> dict:
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (await db.execute(query.order_by(TrialVideo.created_at.desc(), TrialVideo.id.desc())
                            .offset((page - 1) * page_size).limit(page_size))).all()
    serialize = service.management_data if private else service.public_data
    viewer_id = user.id if user.role == UserRole.STUDENT else None
    return dict(total=total, items=[serialize(video, video.presenter_name if video.source == "example" else name,
                                             college if video.source == "student" else None, viewer_id)
                                   for video, name, college in rows])


def base_query():
    return select(TrialVideo, User.name, User.college).join(User, User.id == TrialVideo.owner_id)


@router.get("/public")
async def public_videos(source: Literal["student", "example"] = "example", page: int = Query(1, ge=1),
                        page_size: int = Query(100, ge=1, le=100), db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    query = base_query().where(TrialVideo.source == source, TrialVideo.is_public.is_(True),
                               TrialVideo.blocked_at.is_(None), TrialVideo.file_name.is_not(None),
                               TrialVideo.file_status == "available", User.is_active.is_(True))
    return await list_rows(db, query, page, page_size, False, user)


@router.get("/mine")
async def my_videos(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    db: AsyncSession = Depends(get_db), user: User = Depends(require_student)):
    return await list_rows(db, base_query().where(TrialVideo.owner_id == user.id, TrialVideo.source == "student"),
                           page, page_size, True, user)


@router.get("/instructor")
async def instructor_videos(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                            db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != UserRole.INSTRUCTOR:
        raise HTTPException(403, "只有指导老师可以访问")
    query = base_query().join(Group, and_(Group.student_id == TrialVideo.owner_id,
        Group.semester_id == TrialVideo.semester_id)).where(Group.instructor_id == user.id, TrialVideo.source == "student")
    return await list_rows(db, query, page, page_size, True, user)


@router.get("/admin")
async def admin_videos(source: Literal["student", "example"] = "example", page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_admin)):
    return dict(await list_rows(db, base_query().where(TrialVideo.source == source), page, page_size, True, user),
                used_bytes=await service.used_bytes(db), total_bytes=settings.TRIAL_VIDEO_TOTAL_BYTES)


@router.patch("/{video_id}")
async def update_video(video_id: int, changes: VideoUpdate, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    async with service.mutation_lock:
        await db.commit()
        video = await get_video(db, video_id)
        if not (user.role == UserRole.ADMIN and video.source == "example" or
                user.role == UserRole.STUDENT and video.owner_id == user.id and video.source == "student"):
            raise HTTPException(403, "无权修改视频")
        if not service.available(video):
            raise HTTPException(410, "原视频已删除或到期，不能重新发布")
        fields = changes.model_dump(exclude_unset=True, exclude_none=True)
        if video.source == "student":
            fields.pop("presenter_name", None)
            fields.pop("presenter_type", None)
        new_public = fields.get("is_public", video.is_public)
        if new_public and video.blocked_at is not None:
            raise HTTPException(403, "视频已被管理员下架，不能自行重新公开")
        if new_public or video.source == "example":
            service.validate_public(fields.get("title", video.title), fields.get("subject", video.subject))
        elif fields.get("subject") and fields["subject"] not in service.SUBJECTS:
            raise HTTPException(422, "请选择有效学科")
        if "presenter_name" in fields and not fields["presenter_name"].strip():
            raise HTTPException(422, "请填写讲授者姓名")
        if new_public != video.is_public:
            video.expires_at = None if new_public or video.source == "example" else (
                service.now() + timedelta(days=settings.TRIAL_VIDEO_PRIVATE_DAYS))
            if new_public:
                video.published_at = service.now()
        for key, value in fields.items():
            setattr(video, key, value.strip() if isinstance(value, str) else value)
        await db.commit()
        await db.refresh(video)
        college = await db.scalar(select(User.college).where(User.id == video.owner_id))
        return service.management_data(video, await author_name(db, video), college,
                                       user.id if user.role == UserRole.STUDENT else None)


@router.post("/{video_id}/takedown")
async def takedown_video(video_id: int, data: Takedown, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_admin)):
    if not data.reason.strip():
        raise HTTPException(422, "请填写下架原因")
    async with service.mutation_lock:
        await db.commit()
        video = await get_video(db, video_id)
        if video.source != "student":
            raise HTTPException(422, "优秀示例请使用下架开关")
        block = await db.scalar(select(TrialVideoBlock).where(
            TrialVideoBlock.owner_id == video.owner_id, TrialVideoBlock.sha256 == video.sha256))
        if block is None:
            db.add(TrialVideoBlock(owner_id=video.owner_id, sha256=video.sha256, reason=data.reason.strip()))
        copies = (await db.scalars(select(TrialVideo).where(TrialVideo.owner_id == video.owner_id,
            TrialVideo.sha256 == video.sha256, TrialVideo.source == "student"))).all()
        for record in copies:
            record.is_public = False
            record.blocked_at = service.now()
            record.moderation_reason = data.reason.strip()
            if record.file_name and record.expires_at is None:
                record.expires_at = service.now() + timedelta(days=settings.TRIAL_VIDEO_PRIVATE_DAYS)
        await db.commit()
    return {"message": "已下架，学生不能自行重新公开该视频"}


@router.delete("/{video_id}")
async def delete_video(video_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    async with service.mutation_lock:
        await db.commit()
        video = await get_video(db, video_id)
        if user.role != UserRole.ADMIN and not (user.role == UserRole.STUDENT and video.owner_id == user.id):
            raise HTTPException(403, "无权删除视频")
        await service.remove_file(video, "deleted")
        await db.commit()
    return {"message": "视频已删除，已有分析报告保留"}


@router.get("/{video_id}/analysis")
async def video_analysis(video_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    video = await get_video(db, video_id)
    if not await service.can_manage_private(db, video, user):
        raise HTTPException(403, "无权查看分析报告")
    return dict(status=video.analysis_status, analysis=video.analysis_result, error=video.analysis_error)


async def discussion_video(db: AsyncSession, video_id: int, user: User) -> TrialVideo:
    if user.role not in (UserRole.STUDENT, UserRole.ADMIN):
        raise HTTPException(403, "评论区仅供学生交流")
    video = await get_video(db, video_id)
    if video.source != "student":
        raise HTTPException(422, "仅同学上传的试讲视频支持评论")
    await service.ensure_can_play(db, video, user)
    if video.blocked_at is not None:
        raise HTTPException(403, "视频已下架，暂不支持评论")
    return video


@router.get("/{video_id}")
async def video_detail(video_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    video = await get_video(db, video_id)
    await service.ensure_can_play(db, video, user)
    owner = await db.get(User, video.owner_id)
    return service.public_data(video, video.presenter_name if video.source == "example" else owner.name,
                               owner.college, user.id if user.role == UserRole.STUDENT else None)


def comment_data(comment: TrialVideoComment, author: User, video: TrialVideo, viewer: User,
                 reply_count: int = 0) -> dict:
    avatar = author.avatar or f"https://api.dicebear.com/7.x/notionists/svg?seed={quote(author.user_code, safe='')}&backgroundColor=b6e3f4,c0aede,d1d4f9"
    return dict(id=comment.id, content=comment.content, author_name=author.name, author_role=author.role.value,
                author_avatar=avatar if not comment.is_deleted else "",
                is_video_author=comment.author_id == video.owner_id, created_at=comment.created_at,
                can_delete=not comment.is_deleted and (comment.author_id == viewer.id or viewer.role == UserRole.ADMIN),
                parent_id=comment.parent_id, is_deleted=comment.is_deleted, reply_count=reply_count)


@router.get("/{video_id}/comments/{comment_id}/context")
async def comment_context(video_id: int, comment_id: int, db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    video = await discussion_video(db, video_id, user)
    thread = []
    identifier = comment_id
    while identifier is not None:
        comment = await db.get(TrialVideoComment, identifier)
        if comment is None or comment.video_id != video_id or identifier in {row.id for row in thread}:
            raise HTTPException(404, "评论不存在或已删除")
        if not thread and comment.is_deleted:
            raise HTTPException(404, "评论已删除")
        thread.append(comment)
        identifier = comment.parent_id
    thread.reverse()
    root = thread[0]
    root_created = select(TrialVideoComment.created_at).where(TrialVideoComment.id == root.id).correlate(None).scalar_subquery()
    preceding = await db.scalar(select(func.count()).select_from(TrialVideoComment).where(
        TrialVideoComment.video_id == video_id, TrialVideoComment.parent_id.is_(None),
        or_(TrialVideoComment.created_at > root_created,
            and_(TrialVideoComment.created_at == root_created, TrialVideoComment.id > root.id))))
    ids = [row.id for row in thread]
    reply_counts = dict((await db.execute(select(TrialVideoComment.parent_id, func.count())
        .where(TrialVideoComment.parent_id.in_(ids)).group_by(TrialVideoComment.parent_id))).all())
    authors = {author.id: author for author in (await db.scalars(select(User).where(
        User.id.in_({row.author_id for row in thread})))).all()}
    return dict(root_page=preceding // 20 + 1,
                thread=[comment_data(row, authors[row.author_id], video, user, reply_counts.get(row.id, 0)) for row in thread])


@router.get("/{video_id}/comments")
async def video_comments(video_id: int, page: int = Query(1, ge=1),
                         page_size: int = Query(20, ge=1, le=50), parent_id: Optional[int] = Query(None, gt=0),
                         db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    video = await discussion_video(db, video_id, user)
    if parent_id is not None:
        parent = await db.get(TrialVideoComment, parent_id)
        if parent is None or parent.video_id != video_id:
            raise HTTPException(404, "被回复的评论不存在")
    conditions = (TrialVideoComment.video_id == video_id, TrialVideoComment.parent_id == parent_id)
    total = await db.scalar(select(func.count()).select_from(TrialVideoComment)
                            .where(*conditions))
    comment_count = await db.scalar(select(func.count()).select_from(TrialVideoComment).where(
        TrialVideoComment.video_id == video_id, TrialVideoComment.is_deleted.is_(False)))
    order = (TrialVideoComment.created_at.asc(), TrialVideoComment.id.asc()) if parent_id is not None else (
        TrialVideoComment.created_at.desc(), TrialVideoComment.id.desc())
    rows = (await db.execute(select(TrialVideoComment, User)
        .join(User, User.id == TrialVideoComment.author_id)
        .where(*conditions)
        .order_by(*order)
        .offset((page - 1) * page_size).limit(page_size))).all()
    ids = [comment.id for comment, _ in rows]
    reply_counts = dict((await db.execute(select(TrialVideoComment.parent_id, func.count())
        .where(TrialVideoComment.video_id == video_id, TrialVideoComment.parent_id.in_(ids))
        .group_by(TrialVideoComment.parent_id))).all()) if ids else {}
    return dict(total=total, comment_count=comment_count, items=[comment_data(comment, author, video, user, reply_counts.get(comment.id, 0))
                                   for comment, author in rows])


@router.post("/{video_id}/comments", status_code=201)
async def create_video_comment(video_id: int, data: CommentCreate, db: AsyncSession = Depends(get_db),
                               user: User = Depends(require_student)):
    async with service.mutation_lock:
        # Serialize against video deletion, takedown and visibility changes.
        await db.commit()
        video = await discussion_video(db, video_id, user)
        parent = None
        if data.parent_id is not None:
            parent = await db.get(TrialVideoComment, data.parent_id)
            if parent is None or parent.video_id != video_id:
                raise HTTPException(404, "被回复的评论不存在")
            if parent.is_deleted:
                raise HTTPException(410, "该评论已删除，请回复其他评论")
        comment = TrialVideoComment(video_id=video.id, author_id=user.id, content=data.content, parent_id=data.parent_id)
        db.add(comment)
        await db.flush()
        recipients = {video.owner_id: "评论了你的试讲"}
        if parent is not None:
            recipients[parent.author_id] = "回复了你的评论"
        recipients.pop(user.id, None)
        if recipients:
            eligible = (await db.scalars(select(User.id).where(User.id.in_(recipients),
                User.role == UserRole.STUDENT, User.is_active.is_(True)))).all()
            for recipient in eligible:
                db.add(Notification(user_id=recipient, type="comment",
                    title=f"{user.name}{recipients[recipient]}", content=f"《{video.title}》\n{comment.content}",
                    link=f"/student/trial-learning?tab=student&video={video.id}&comment={comment.id}"))
        await db.commit()
        await db.refresh(comment)
        return comment_data(comment, user, video, user)


@router.delete("/{video_id}/comments/{comment_id}")
async def delete_video_comment(video_id: int, comment_id: int, db: AsyncSession = Depends(get_db),
                               user: User = Depends(get_current_user)):
    async with service.mutation_lock:
        await db.commit()
        await discussion_video(db, video_id, user)
        comment = await db.scalar(select(TrialVideoComment).where(
            TrialVideoComment.id == comment_id, TrialVideoComment.video_id == video_id))
        if comment is None or comment.is_deleted:
            raise HTTPException(404, "评论不存在或已删除")
        if comment.author_id != user.id and user.role != UserRole.ADMIN:
            raise HTTPException(403, "只能删除自己的评论")
        children = await db.scalar(select(func.count()).select_from(TrialVideoComment).where(
            TrialVideoComment.parent_id == comment.id))
        if children:
            # Preserve classmates' replies when the original comment is removed.
            comment.content = ""
            comment.is_deleted = True
        else:
            parent_id = comment.parent_id
            await db.delete(comment)
            await db.flush()
            # Remove empty placeholders once their last reply is deleted.
            while parent_id is not None:
                parent = await db.get(TrialVideoComment, parent_id)
                if parent is None or not parent.is_deleted:
                    break
                remaining = await db.scalar(select(func.count()).select_from(TrialVideoComment).where(
                    TrialVideoComment.parent_id == parent.id))
                if remaining:
                    break
                parent_id = parent.parent_id
                await db.delete(parent)
                await db.flush()
        await db.commit()
    return {"message": "评论已删除"}


@router.post("/{video_id}/playback")
async def playback(video_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    video = await get_video(db, video_id)
    await service.ensure_can_play(db, video, user)
    if not service.file_path(video).is_file():
        raise HTTPException(410, "视频文件已不存在")
    return {"url": f"/api/v1/trial-videos/{video_id}/stream?ticket={service.create_ticket(video_id, user.id)}"}


@router.get("/{video_id}/cover")
async def video_cover(video_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    video = await get_video(db, video_id)
    await service.ensure_can_play(db, video, user)
    if not service.file_path(video).is_file():
        raise HTTPException(410, "视频文件已不存在")
    cover = await service.ensure_cover(video)
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if cover:
        return FileResponse(cover, media_type="image/jpeg", headers=headers)
    return Response(service.DEFAULT_COVER, media_type="image/svg+xml", headers=headers)


@router.get("/{video_id}/stream")
async def stream_video(video_id: int, request: Request, ticket: str = Query(...), db: AsyncSession = Depends(get_db)):
    viewer = service.ticket_viewer(ticket, video_id)
    user = await db.get(User, viewer)
    if user is None or not user.is_active:
        raise HTTPException(401, "用户不存在或已停用")
    video = await get_video(db, video_id)
    await service.ensure_can_play(db, video, user)
    path = service.file_path(video)
    if not path.is_file():
        raise HTTPException(410, "视频文件已不存在")
    size = path.stat().st_size
    start, end, status = service.byte_range(request.headers.get("range"), size)
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1),
               "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
               "Referrer-Policy": "no-referrer"}
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(service.stream_chunks(path, start, end), status_code=status,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", headers=headers)
