"""Owner-scoped background video recommendations and confirmed references."""
import json
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.lesson_video import LessonVideo, LessonVideoSearch, LessonWebResource
from app.models.user import User
from app.services.audio_resources import owned_audio_lesson
from app.services.lesson_videos import current_fingerprint, parse_video_url, queue_search, run_search, search_state

from app.services.bilibili_metadata import cover_url, video_metadata

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field('', max_length=160)
    force: bool = False


class VideoRequest(BaseModel):
    candidate_id: str | None = Field(None, max_length=32)
    url: str = Field('', max_length=1024)
    title: str = Field('', max_length=256)
    section: str = Field('', max_length=100)
    purpose: str = Field('', max_length=400)


@router.get('/audio-lessons/{lesson_id}/videos')
async def videos(lesson_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = await owned_audio_lesson(db, user.id, lesson_id)
    return await search_state(db, lesson)


@router.get('/audio-lessons/{lesson_id}/videos/{bvid}/metadata')
async def metadata(lesson_id: int, bvid: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await owned_audio_lesson(db, user.id, lesson_id)
    if not re.fullmatch(r'BV[0-9A-Za-z]{10}', bvid):
        raise HTTPException(404, '该资源不支持视频元数据查询')
    state = (await db.execute(select(LessonVideoSearch).where(LessonVideoSearch.lesson_id == lesson_id))).scalar_one_or_none()
    candidate = next((item for item in json.loads(state.items_json) if item.get('bvid') == bvid), None) if state else None
    saved = (await db.execute(select(LessonVideo.id).where(LessonVideo.lesson_id == lesson_id,
        LessonVideo.bvid == bvid).limit(1))).scalar_one_or_none()
    if not candidate and not saved:
        raise HTTPException(404, '视频引用不存在')
    result = await video_metadata(bvid)
    if not result['cover_url'] and candidate:
        result['cover_url'] = cover_url(candidate.get('cover_url'))
    return result


@router.post('/audio-lessons/{lesson_id}/videos/search')
async def search(lesson_id: int, body: SearchRequest, background_tasks: BackgroundTasks,
                 db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = await owned_audio_lesson(db, user.id, lesson_id)
    run_id = await queue_search(db, lesson, query=body.query.strip(), force=body.force)
    if run_id:
        background_tasks.add_task(run_search, db.bind, lesson_id, user.id, run_id)
    return await search_state(db, lesson)


@router.post('/audio-lessons/{lesson_id}/videos')
async def add(lesson_id: int, body: VideoRequest,
              db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = await owned_audio_lesson(db, user.id, lesson_id)
    if body.candidate_id:
        state = (await db.execute(select(LessonVideoSearch).where(LessonVideoSearch.lesson_id == lesson_id))).scalar_one_or_none()
        candidate = next((item for item in json.loads(state.items_json) if item['id'] == body.candidate_id), None) if state else None
        if not candidate or state.fingerprint != await current_fingerprint(db, lesson, state.query):
            raise HTTPException(409, '推荐结果已更新，请刷新后重新选择')
        bvid, page = candidate['bvid'], candidate['page']
        title, section, purpose, source = candidate['title'], candidate['section'], candidate['purpose'], 'bocha'
    else:
        try:
            bvid, page = parse_video_url(body.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        title, section, purpose, source = body.title.strip(), body.section.strip(), body.purpose.strip(), 'manual'
        if not title or not section or not purpose:
            raise HTTPException(422, '请填写视频标题、教学环节和视频用途')
    exists = (await db.execute(select(LessonVideo.id).where(LessonVideo.lesson_id == lesson_id,
        LessonVideo.bvid == bvid, LessonVideo.page == page))).scalar_one_or_none()
    if not exists:
        count = (await db.execute(select(func.count()).select_from(LessonVideo).where(LessonVideo.lesson_id == lesson_id))).scalar_one()
        if count >= 30:
            raise HTTPException(422, '每份教案最多保存30个视频，请先移除不再使用的视频')
        try:
            async with db.begin_nested():
                db.add(LessonVideo(lesson_id=lesson_id, bvid=bvid, page=page, title=title,
                                   section=section, purpose=purpose, source=source))
                await db.flush()
        except IntegrityError:
            pass  # A concurrent double-click has already saved the same video.
        await db.commit()
    return await search_state(db, lesson)


@router.delete('/audio-lessons/{lesson_id}/videos/{video_id}')
async def remove(lesson_id: int, video_id: str,
                 db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = await owned_audio_lesson(db, user.id, lesson_id)
    model = LessonWebResource if re.fullmatch(r'web-[1-9]\d*', video_id) else LessonVideo
    identifier = video_id[4:] if model is LessonWebResource else video_id
    if not identifier.isdecimal() or len(identifier) > 18:
        raise HTTPException(404, '资源引用不存在')
    item = (await db.execute(select(model).where(model.id == int(identifier), model.lesson_id == lesson_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(404, '视频引用不存在')
    await db.delete(item)
    await db.commit()
    return await search_state(db, lesson)
