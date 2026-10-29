"""Shared teaching tips; only administrators can manage their publication."""
import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_admin
from app.models.teaching_tip import TeachingTipVideo
from app.models.user import User
from app.services.bilibili_metadata import video_page_metadata
from app.services.lesson_videos import parse_video_url, video_links
from app.services.teaching_tip_covers import MAX_COVER_BYTES, is_local_cover, normalized_cover_url, store_cover

router = APIRouter()


class TipRequest(BaseModel):
    url: str = Field(min_length=1, max_length=1024)
    title: str = Field(min_length=1, max_length=256)
    category: str = Field('试讲技巧', min_length=1, max_length=64)
    description: str = Field('', max_length=2000)
    cover_url: str = Field('', max_length=2048)
    sort_order: int = Field(0, ge=0, le=99999)
    is_published: bool = False

    @field_validator('title', 'category', 'description', 'url', 'cover_url', mode='before')
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('cover_url')
    @classmethod
    def validate_cover(cls, value):
        normalized = normalized_cover_url(value)
        if value and not normalized:
            raise ValueError('请上传封面图片，或使用有效的 B 站视频封面链接')
        return normalized


class MetadataRequest(BaseModel):
    url: str = Field(min_length=1, max_length=1024)


def parse_url(value):
    try:
        return parse_video_url(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


def serialize(item):
    return dict(id=item.id, bvid=item.bvid, page=item.page, title=item.title,
                category=item.category, description=item.description, cover_url=item.cover_url,
                sort_order=item.sort_order, is_published=item.is_published,
                url=video_links(item.bvid, item.page)['url'])


@router.get('/resources/teaching-tips')
async def published(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.scalars(select(TeachingTipVideo).where(TeachingTipVideo.is_published.is_(True))
        .order_by(TeachingTipVideo.sort_order, TeachingTipVideo.id.desc()))).all()
    return dict(items=[serialize(row) for row in rows])


@router.get('/admin/teaching-tips')
async def listing(db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    rows = (await db.scalars(select(TeachingTipVideo)
        .order_by(TeachingTipVideo.sort_order, TeachingTipVideo.id.desc()))).all()
    return dict(items=[serialize(row) for row in rows])


@router.get('/resources/teaching-tips/{identifier}/metadata')
async def published_metadata(identifier: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    item = await find(db, identifier)
    if not item.is_published:
        raise HTTPException(404, '试讲技巧视频不存在')
    if is_local_cover(item.cover_url):
        return dict(cover_url=item.cover_url)
    result = await video_page_metadata(item.bvid)
    return dict(cover_url=result['cover_url'] or item.cover_url)


@router.post('/admin/teaching-tips/metadata')
async def metadata(body: MetadataRequest, user: User = Depends(require_admin)):
    bvid, _ = parse_url(body.url)
    return await video_page_metadata(bvid)


@router.post('/admin/teaching-tips/covers', status_code=201)
async def upload_cover(file: UploadFile = File(...), user: User = Depends(require_admin)):
    try:
        raw = await file.read(MAX_COVER_BYTES + 1)
    finally:
        await file.close()
    try:
        url = await asyncio.to_thread(store_cover, raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except OSError:
        raise HTTPException(503, '封面保存失败，请稍后重试') from None
    return dict(cover_url=url)


async def save(db, body, item=None):
    bvid, page = parse_url(body.url)
    if item is None:
        item = TeachingTipVideo()
        db.add(item)
    item.bvid, item.page = bvid, page
    for key, value in body.model_dump(exclude={'url'}).items():
        setattr(item, key, value)
    if not item.cover_url:
        item.cover_url = (await video_page_metadata(bvid))['cover_url']
    try:
        await db.commit()
        await db.refresh(item)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, '该视频分集已添加，请编辑已有视频') from None
    return serialize(item)


@router.post('/admin/teaching-tips', status_code=201)
async def create(body: TipRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    return await save(db, body)


async def find(db, identifier):
    item = await db.get(TeachingTipVideo, identifier)
    if item is None:
        raise HTTPException(404, '试讲技巧视频不存在')
    return item


@router.put('/admin/teaching-tips/{identifier}')
async def update(identifier: int, body: TipRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    return await save(db, body, await find(db, identifier))


@router.delete('/admin/teaching-tips/{identifier}', status_code=204)
async def remove(identifier: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)):
    await db.delete(await find(db, identifier))
    await db.commit()
