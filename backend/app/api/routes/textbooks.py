"""Administrator ingestion/review and authenticated chapter/material retrieval."""
import asyncio
import io
import json
import uuid
import hashlib
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_admin
from app.models.user import UserRole
from app.models.textbook import Textbook, TextbookPage, TextbookChapter, TextbookAsset, TextbookLesson
from app.services.textbook_service import private_path, ingest_pdf, lesson_context, chapter_assets, lesson_bundle, search_assets, asset_metadata
from app.services.textbook_catalog import STAGES, FILENAME, school_stage, display_title, clean_chapter_title, is_removed_chapter
from app.services.textbook_outline import reviewed_directory, title_key
from app.services.textbook_units import group_chapter_directory
from app.services.textbook_physics import is_highschool_physics, physics_heading_title
from app.services.textbook_chemistry import is_highschool_chemistry, chemistry_heading_title
from pathlib import Path

router = APIRouter()


class ChapterInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    parent_title: str = Field(default='', max_length=160)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    printed_pages: str = Field(default='', max_length=80)
    content: Optional[str] = Field(default=None, max_length=48000)
    is_published: bool = False


class AssetInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    chapter_id: Optional[int] = Field(default=None, gt=0)
    figure_number: str = Field(default='', max_length=60)
    description: str = Field(default='', max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    conditions: str = Field(default='', max_length=2000)
    is_reviewed: bool = False


class BookInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=40)
    grade: str = Field(min_length=1, max_length=30)
    publisher: str = Field(default='', max_length=100)
    edition: str = Field(default='', max_length=160)
    volume: str = Field(default='', max_length=80)


def admin_user(user):
    return user.role == UserRole.ADMIN


def book_data(book):
    return {**{key: getattr(book, key) for key in ('id', 'title', 'subject', 'grade', 'publisher', 'edition',
            'volume', 'original_filename', 'page_count', 'status', 'is_published')},
            'stage': school_stage(book.grade), 'display_title': display_title(book)}


def filter_grade(query, selection):
    if selection in STAGES:
        return query.where(Textbook.grade.startswith(selection))
    return query.where(Textbook.grade == selection) if selection else query


def chapter_data(chapter, *, content=False):
    result = {key: getattr(chapter, key) for key in ('id', 'book_id', 'title', 'parent_title', 'start_page',
              'end_page', 'printed_pages', 'is_published')}
    if content:
        result['content'] = chapter.content
    return result


def image_data(image):
    result = {key: getattr(image, key) for key in ('asset_id', 'book_id', 'chapter_id', 'title', 'pdf_page',
              'figure_number', 'description', 'conditions', 'width', 'height', 'is_reviewed')}
    result['tags'] = json.loads(image.tags_json)
    return result


async def visible_book(db, book_id, user):
    book = await db.get(Textbook, book_id)
    if not book or (not book.is_published and not admin_user(user)):
        raise HTTPException(404, '教材不存在')
    return book


@router.get('')
async def list_books(subject: str = '', grade: str = '', stage: str = '', catalog_only: bool = False,
                     db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    query = select(Textbook).order_by(Textbook.id.desc())
    if not admin_user(user):
        query = query.where(Textbook.is_published == True)
    if subject:
        query = query.where(Textbook.subject == subject)
    if stage and stage not in STAGES:
        raise HTTPException(422, '学段须为小学、初中或高中')
    query = filter_grade(query, grade)
    query = filter_grade(query, stage)
    books = (await db.execute(query)).scalars().all()
    if catalog_only:
        books = [book for book in books if FILENAME.fullmatch(Path(book.original_filename).stem)]
    return {'success': True, 'data': [book_data(b) for b in books]}


@router.post('', status_code=201)
async def upload_book(file: UploadFile = File(...), title: str = Form(..., min_length=1, max_length=160),
    subject: str = Form(..., min_length=1, max_length=40), grade: str = Form(..., min_length=1, max_length=30),
    publisher: str = Form('', max_length=100), edition: str = Form('', max_length=160), volume: str = Form('', max_length=80),
    db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    raw = await file.read(80 * 1024 * 1024 + 1)
    if len(raw) > 80 * 1024 * 1024:
        raise HTTPException(413, '教材PDF最多80MB')
    book = await ingest_pdf(db, raw, file.filename or 'textbook.pdf',
                           dict(title=title, subject=subject, grade=grade, publisher=publisher, edition=edition, volume=volume))
    return {'success': True, 'data': book_data(book)}


@router.get('/recommend')
async def recommend(subject: str, grade: str, topic: str = Query('', max_length=160), book_id: Optional[int] = None,
                    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    query = select(TextbookChapter, Textbook).join(Textbook, Textbook.id == TextbookChapter.book_id).where(
        TextbookChapter.is_published == True, Textbook.is_published == True, Textbook.subject == subject)
    query = filter_grade(query, grade)
    if book_id:
        query = query.where(Textbook.id == book_id)
    rows = (await db.execute(query)).all()
    def score(title):
        if topic and topic in title:
            return 100 + len(topic)
        return sum(1 for i in range(max(0, len(topic) - 1)) if topic[i:i+2] in title)
    items = [{**chapter_data(c), 'book_title': b.title, 'edition': b.edition, 'volume': b.volume,
              'score': score(c.title)} for c, b in rows if not is_removed_chapter(b.subject, c.title, b.grade, b.sha256)
              and not (is_highschool_physics(b) and physics_heading_title(c.title))
              and not (is_highschool_chemistry(b) and chemistry_heading_title(c.title))]
    items.sort(key=lambda item: (-item['score'], item['book_id'], item['start_page']))
    return {'success': True, 'data': items[:30]}


@router.get('/assets/{asset_id}/image')
async def image_file(asset_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    image = (await db.execute(select(TextbookAsset).where(TextbookAsset.asset_id == asset_id))).scalar_one_or_none()
    if not image:
        raise HTTPException(404, '图片不存在')
    book = await visible_book(db, image.book_id, user)
    chapter = await db.get(TextbookChapter, image.chapter_id) if image.chapter_id else None
    if not admin_user(user) and (not image.is_reviewed or not chapter or not chapter.is_published):
        raise HTTPException(404, '图片尚未发布')
    path = private_path(image.file_path)
    if not path.is_file():
        raise HTTPException(404, '图片文件缺失')
    return FileResponse(path, media_type='image/png', headers={'Cache-Control': 'private, no-store'})


@router.patch('/assets/{asset_id}')
async def update_asset(asset_id: str, body: AssetInput, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    image = (await db.execute(select(TextbookAsset).where(TextbookAsset.asset_id == asset_id))).scalar_one_or_none()
    if not image:
        raise HTTPException(404, '图片不存在')
    if body.chapter_id:
        chapter = await db.get(TextbookChapter, body.chapter_id)
        if not chapter or chapter.book_id != image.book_id or not chapter.start_page <= image.pdf_page <= chapter.end_page:
            raise HTTPException(422, '图片须关联同教材、同页范围内的章节')
    if any(not 1 <= len(tag.strip()) <= 60 for tag in body.tags):
        raise HTTPException(422, '图片标签须为1–60字符')
    if body.is_reviewed and (not body.chapter_id or not body.tags or not body.description.strip()):
        raise HTTPException(422, '核对图片前请填写章节、标签和内容说明')
    for key, value in body.model_dump(exclude={'tags'}).items():
        setattr(image, key, value)
    image.tags_json = json.dumps([tag.strip() for tag in body.tags], ensure_ascii=False)
    await db.commit()
    return {'success': True, 'data': image_data(image)}


@router.get('/chapters/{chapter_id}')
async def get_chapter(chapter_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    chapter = await db.get(TextbookChapter, chapter_id)
    if not chapter:
        raise HTTPException(404, '章节不存在')
    book = await visible_book(db, chapter.book_id, user)
    if is_removed_chapter(book.subject, chapter.title, book.grade, book.sha256):
        raise HTTPException(404, '章节已移除')
    if not chapter.is_published and not admin_user(user):
        raise HTTPException(404, '章节尚未发布')
    images = await chapter_assets(db, chapter, book)
    return {'success': True, 'data': {**chapter_data(chapter, content=True), 'assets': images}}


async def save_chapter(db, book, body, existing=None):
    if is_removed_chapter(book.subject, body.title, book.grade, book.sha256):
        raise HTTPException(422, '物理教材不再收录此类导读或补充目录项' if book.subject == '物理'
                            else '历史教材不再收录附录、其他章节占位项及译名对照表（下）' if book.subject == '历史'
                            else '地理教材不再收录附录、其他章节占位项、后记及出版信息，初中地理不再收录主题活动' if book.subject == '地理'
                            else '高中生物不再收录附录' if book.subject == '生物'
                            else '高中化学目录仅收录正式章、节及实验活动' if is_highschool_chemistry(book)
                            else '初中化学不再收录绪论、整理与提高（提升）、复习与提高及附录' if book.subject == '化学'
                            else '英语教材不再收录此类补充目录项' if book.subject == '英语'
                            else '小学语文不再收录字词附表等补充目录项' if book.subject == '语文'
                            else '数学教材不再收录小结、数学活动、复习题及词汇索引')
    if not body.start_page <= body.end_page <= book.page_count:
        raise HTTPException(422, '章节PDF页码超出教材范围')
    content = body.content
    if content is None:
        pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book.id,
                 TextbookPage.page_number.between(body.start_page, body.end_page)).order_by(TextbookPage.page_number))).scalars().all()
        content = '\n\n'.join(f'[PDF第{p.page_number}页]\n{p.content}' for p in pages)
    if not content.strip() or len(content) > 48000:
        raise HTTPException(422, '章节正文为空或过长，请核对文字或拆分小节')
    if body.is_published and len(re.sub(r'\[PDF第\d+页\]', '', content).strip()) < 40:
        raise HTTPException(422, '正文不足，不能将空白扫描页或页码标记作为已核对教材发布')
    if existing and (body.start_page != existing.start_page or body.end_page != existing.end_page):
        images = (await db.execute(select(TextbookAsset).where(TextbookAsset.chapter_id == existing.id))).scalars().all()
        for image in images:
            if not body.start_page <= image.pdf_page <= body.end_page:
                image.chapter_id, image.is_reviewed = None, False
    chapter = existing or TextbookChapter(book_id=book.id)
    for key, value in body.model_dump(exclude={'content'}).items():
        if key in ('title', 'parent_title'):
            value = clean_chapter_title(value)
        setattr(chapter, key, value)
    chapter.content = content
    db.add(chapter)
    if body.is_published:
        book.is_published = True
    await db.commit()
    return chapter


@router.put('/chapters/{chapter_id}')
async def edit_chapter(chapter_id: int, body: ChapterInput, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    chapter = await db.get(TextbookChapter, chapter_id)
    if not chapter:
        raise HTTPException(404, '章节不存在')
    book = await db.get(Textbook, chapter.book_id)
    chapter = await save_chapter(db, book, body, chapter)
    return {'success': True, 'data': chapter_data(chapter, content=True)}


@router.get('/lessons/{lesson_id}/bundle')
async def download_lesson(lesson_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    lesson = (await db.execute(select(TextbookLesson).where(TextbookLesson.id == lesson_id, TextbookLesson.user_id == user.id))).scalar_one_or_none()
    if not lesson:
        raise HTTPException(404, '教案不存在')
    return Response(await lesson_bundle(db, lesson), media_type='application/zip',
                    headers={'Content-Disposition': 'attachment; filename="lesson-with-images.zip"', 'Cache-Control': 'private, no-store'})


@router.get('/{book_id}/chapters')
async def list_chapters(book_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    book = await visible_book(db, book_id, user)
    query = select(TextbookChapter).where(TextbookChapter.book_id == book_id).order_by(TextbookChapter.start_page, TextbookChapter.id)
    if not admin_user(user):
        query = query.where(TextbookChapter.is_published == True)
    chapters = (await db.execute(query)).scalars().all()
    review = reviewed_directory(book.sha256)
    if review:
        directory_order = {(entry['printed']+review['offset'],title_key(entry['title'])):index
                           for index,entry in enumerate(review['entries'])}
        chapters.sort(key=lambda chapter:(chapter.start_page,
            directory_order.get((chapter.start_page,title_key(chapter.title)),len(directory_order)),chapter.id))
    directory = await asyncio.to_thread(group_chapter_directory, book, [chapter_data(c) for c in chapters])
    return {'success': True, 'data': directory}


@router.post('/{book_id}/chapters', status_code=201)
async def create_chapter(book_id: int, body: ChapterInput, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    book = await visible_book(db, book_id, user)
    chapter = await save_chapter(db, book, body)
    return {'success': True, 'data': chapter_data(chapter, content=True)}


@router.get('/{book_id}/assets')
async def list_assets(book_id: int, start_page: Optional[int] = None, end_page: Optional[int] = None,
                      db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    await visible_book(db, book_id, user)
    query = select(TextbookAsset).where(TextbookAsset.book_id == book_id).order_by(TextbookAsset.pdf_page, TextbookAsset.id)
    if start_page:
        query = query.where(TextbookAsset.pdf_page >= start_page)
    if end_page:
        query = query.where(TextbookAsset.pdf_page <= end_page)
    return {'success': True, 'data': [image_data(a) for a in (await db.execute(query)).scalars().all()]}


@router.post('/{book_id}/assets', status_code=201)
async def upload_asset(book_id: int, file: UploadFile = File(...), pdf_page: int = Form(..., ge=1),
                       db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    """Add a manually cropped figure when the PDF uses scans/vector drawings."""
    book = await visible_book(db, book_id, user)
    if pdf_page > book.page_count:
        raise HTTPException(422, '图片来源PDF页码超出教材范围')
    raw = await file.read(12 * 1024 * 1024 + 1)
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, '教材图片最多12MB')
    def decode():
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError('图片像素过多')
            image.load()
            result = io.BytesIO()
            image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(result, 'PNG')
            return result.getvalue(), image.width, image.height
    try:
        data, width, height = await asyncio.to_thread(decode)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, '图片格式无效或像素过多，请上传PNG/JPEG等常规图片') from exc
    identifier = 'tb-' + uuid.uuid4().hex
    relative = f'{private_path(book.file_path).parent.name}/images/{identifier}.png'
    destination = private_path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    image = TextbookAsset(book_id=book.id, asset_id=identifier, file_path=relative, pdf_page=pdf_page,
                         title=f'PDF第{pdf_page}页手动裁图', width=width, height=height,
                         sha256=hashlib.sha256(data).hexdigest(), is_reviewed=False)
    db.add(image)
    await db.commit()
    return {'success': True, 'data': image_data(image)}


@router.get('/{book_id}/pages/{number}')
async def page_text(book_id: int, number: int, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    await visible_book(db, book_id, user)
    page = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book_id, TextbookPage.page_number == number))).scalar_one_or_none()
    if not page:
        raise HTTPException(404, '教材页不存在')
    return {'success': True, 'data': {'page_number': number, 'content': page.content}}


@router.get('/{book_id}/pdf')
async def original_pdf(book_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    book = await visible_book(db, book_id, user)
    return FileResponse(private_path(book.file_path), media_type='application/pdf', headers={'Cache-Control': 'private, no-store'})


@router.patch('/{book_id}')
async def edit_book(book_id: int, body: BookInput, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    book = await visible_book(db, book_id, user)
    for key, value in body.model_dump().items():
        setattr(book, key, value)
    await db.commit()
    return {'success': True, 'data': book_data(book)}
