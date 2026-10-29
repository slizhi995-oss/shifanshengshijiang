"""Private lesson resource lists, derived from the owner's saved lesson content."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.textbook import Textbook, TextbookAsset, TextbookChapter, TextbookLesson
from app.models.user import User
from app.services.lesson_resources import lesson_material_references

router = APIRouter()


def lesson_summary(lesson, chapter, book):
    try:
        source = json.loads(lesson.sources_json)
        if not isinstance(source, dict):
            source = {}
    except (ValueError, TypeError):
        source = {}
    # Return citation fields only; historical source metadata may contain other data.
    source = {key: source.get(key) for key in (
        'book_title', 'edition', 'volume', 'chapter_title', 'start_page', 'end_page', 'printed_pages')}
    source['book_id'] = book.id if book else None
    source['chapter_id'] = chapter.id if chapter else None
    source['available'] = bool(book and chapter and book.is_published and chapter.is_published)
    images, pending = lesson_material_references(lesson.content)
    return {
        'id': lesson.id, 'title': lesson.title,
        'subject': book.subject if book else '', 'grade': book.grade if book else '',
        'created_at': lesson.created_at.isoformat() if lesson.created_at else None,
        'source': source, 'image_count': len(images), 'pending_count': len(pending),
    }


def lesson_query(user_id):
    return (select(TextbookLesson, TextbookChapter, Textbook)
            .outerjoin(TextbookChapter, TextbookChapter.id == TextbookLesson.chapter_id)
            .outerjoin(Textbook, Textbook.id == TextbookChapter.book_id)
            .where(TextbookLesson.user_id == user_id))


@router.get('/lessons')
async def list_lesson_resources(
    keyword: str = Query('', max_length=160), page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    query = lesson_query(user.id)
    if keyword.strip():
        keyword_match = f'%{keyword.strip()}%'
        query = query.where(or_(TextbookLesson.title.ilike(keyword_match), Textbook.title.ilike(keyword_match),
                                Textbook.subject.ilike(keyword_match), TextbookChapter.title.ilike(keyword_match)))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(TextbookLesson.created_at.desc(), TextbookLesson.id.desc())
                             .offset((page - 1) * page_size).limit(page_size))).all()
    return {'items': [lesson_summary(*row) for row in rows], 'total': total, 'page': page, 'page_size': page_size}


@router.get('/lessons/{lesson_id}')
async def get_lesson_resources(lesson_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    row = (await db.execute(lesson_query(user.id).where(TextbookLesson.id == lesson_id))).first()
    if not row:
        raise HTTPException(404, '教案不存在')
    lesson, chapter, book = row
    result = lesson_summary(*row)
    references, pending = lesson_material_references(lesson.content)
    images = (await db.execute(select(TextbookAsset).where(TextbookAsset.asset_id.in_(references)))).scalars().all() if references else []
    catalog = {image.asset_id: image for image in images}
    materials = []
    for identifier, usages in references.items():
        image = catalog.get(identifier)
        # A broken/cross-chapter reference must never reveal another chapter's material.
        available = bool(result['source']['available'] and image and image.is_reviewed
                         and image.book_id == book.id and image.chapter_id == chapter.id)
        materials.append({
            'asset_id': identifier, 'available': available,
            'title': image.title if available else '原引用图片暂不可用',
            'figure_number': image.figure_number if available else '',
            'pdf_page': image.pdf_page if available else None,
            'description': image.description if available else '',
            'conditions': image.conditions.removeprefix('[自动提取及视觉核对]').strip() if available else '', 'usages': usages,
        })
    return {**result, 'content': lesson.content, 'materials': materials, 'pending': pending}
