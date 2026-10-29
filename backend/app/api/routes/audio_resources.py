"""Generated lessons and their matched English audio, scoped to the owner."""
import json
import re
from urllib.parse import quote

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.audio_resource import AudioLesson, AudioResource, AudioVectorIndex
from app.models.user import User
from app.services.audio_resources import (
    backfill_audio_lessons, lesson_audio_items, match_lesson_audio, matched_audio_file, owned_audio_lesson,
)

router = APIRouter()


def summary(lesson):
    source = json.loads(lesson.source_json)
    return dict(id=lesson.id, textbook_lesson_id=lesson.textbook_lesson_id, title=lesson.title,
                subject=lesson.subject, grade=lesson.grade,
                created_at=lesson.created_at.isoformat() if lesson.created_at else None,
                audio_count=len(json.loads(lesson.matches_json)), match_status=lesson.match_status,
                source={key: source.get(key) for key in ('book_title', 'edition', 'volume', 'chapter_title', 'parent_title', 'printed_pages')})


@router.get('/audio-status')
async def audio_status(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    total = (await db.execute(select(func.count(AudioResource.id)))).scalar_one()
    ready = (await db.execute(select(func.count(AudioResource.id)).where(
        AudioResource.available == True, AudioResource.eligible == True))).scalar_one()
    pending = (await db.execute(select(func.count(AudioResource.id)).where(AudioResource.eligible == False))).scalar_one()
    books = (await db.execute(select(func.count(func.distinct(AudioResource.textbook_sha256))))).scalar_one()
    index = await db.get(AudioVectorIndex, 1)
    return dict(total=total, ready=ready, pending_review=pending, book_count=books, indexed=bool(index))


@router.get('/audio-lessons')
async def audio_lessons(
    keyword: str = Query('', max_length=160), page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    await backfill_audio_lessons(db, user.id)
    query = select(AudioLesson).where(AudioLesson.user_id == user.id)
    if keyword.strip():
        pattern = f'%{keyword.strip()}%'
        query = query.where(or_(AudioLesson.title.ilike(pattern), AudioLesson.subject.ilike(pattern),
                                AudioLesson.grade.ilike(pattern), AudioLesson.source_json.ilike(pattern)))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    lessons = (await db.execute(query.order_by(AudioLesson.created_at.desc(), AudioLesson.id.desc())
        .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    for lesson in lessons:
        await match_lesson_audio(db, lesson)
    await db.commit()
    return dict(items=[summary(lesson) for lesson in lessons], total=total, page=page, page_size=page_size)


@router.get('/audio-lessons/by-textbook/{textbook_lesson_id}')
async def resolve_lesson(textbook_lesson_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await backfill_audio_lessons(db, user.id)
    lesson = (await db.execute(select(AudioLesson).where(AudioLesson.user_id == user.id,
        AudioLesson.textbook_lesson_id == textbook_lesson_id))).scalar_one_or_none()
    if not lesson:
        raise HTTPException(404, '教案资源不存在')
    await match_lesson_audio(db, lesson)
    await db.commit()
    return summary(lesson)


@router.get('/audio-lessons/{lesson_id}')
async def audio_lesson(lesson_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = await owned_audio_lesson(db, user.id, lesson_id)
    items = await lesson_audio_items(db, lesson)
    await db.commit()
    return {**summary(lesson), 'content': lesson.content, 'audios': items}


@router.post('/audio-lessons/{lesson_id}/rematch')
async def rematch_audio(lesson_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = await owned_audio_lesson(db, user.id, lesson_id)
    await match_lesson_audio(db, lesson, force=True)
    items = await lesson_audio_items(db, lesson)
    await db.commit()
    return {**summary(lesson), 'content': lesson.content, 'audios': items}


@router.get('/audio-lessons/{lesson_id}/audio/{resource_id}/file')
async def audio_file(lesson_id: int, resource_id: str, request: Request,
                     db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    path = await matched_audio_file(db, user.id, lesson_id, resource_id)
    size = path.stat().st_size
    first, last, status = 0, size - 1, 200
    requested_range = request.headers.get('range')
    if requested_range is not None:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested_range.strip())
        if not match or not any(match.groups()):
            raise HTTPException(416, headers={'Content-Range': f'bytes */{size}'})
        if match[1]:
            first, last = int(match[1]), min(int(match[2]), size - 1) if match[2] else size - 1
        else:
            first = max(0, size - int(match[2]))
        status = 206
    if first > last or first >= size:
        raise HTTPException(416, headers={'Content-Range': f'bytes */{size}'})

    async def chunks():
        async with aiofiles.open(path, 'rb') as source:
            await source.seek(first)
            remaining = last - first + 1
            while remaining:
                block = await source.read(min(256 * 1024, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block

    headers = {'Accept-Ranges': 'bytes', 'Content-Length': str(last - first + 1),
               'Content-Disposition': f"inline; filename*=UTF-8''{quote(path.name)}",
               'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'}
    if status == 206:
        headers['Content-Range'] = f'bytes {first}-{last}/{size}'
    return StreamingResponse(chunks(), status_code=status, media_type='audio/mpeg', headers=headers)
