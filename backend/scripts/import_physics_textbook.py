"""Import the already visually checked Newton chapter and its four native images.

This is a local administrator bootstrap for the supplied PDF, not whole-book review.
Run from backend: python -m scripts.import_physics_textbook --pdf PATH --manifest PATH
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from sqlalchemy import select
from app.core.database import engine, async_session_factory
from app.models.base import Base
from app.models.textbook import TextbookChapter, TextbookPage, TextbookAsset
from app.services.textbook_service import ingest_pdf, private_path


async def main(pdf, manifest):
    sample = json.loads(manifest.read_text(encoding='utf-8'))
    raw = pdf.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sample['source']['sha256']:
        raise ValueError('The checked figure manifest belongs to a different PDF')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as db:
        book = await ingest_pdf(db, raw, pdf.name, dict(title='普通高中教科书 物理 必修第一册',
            subject='物理', grade='高中一年级', publisher='人民教育出版社', edition='人教版（版次待核对）', volume='必修第一册'))
        chapter = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id,
                      TextbookChapter.title == '牛顿第一定律', TextbookChapter.start_page == 88))).scalar_one_or_none()
        if not chapter:
            chapter = TextbookChapter(book_id=book.id, title='牛顿第一定律', parent_title='第四章 运动和力的关系',
                         start_page=88, end_page=92, printed_pages='83–87', content='', is_published=True)
            db.add(chapter)
            await db.flush()
        pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book.id,
                        TextbookPage.page_number.between(88, 92)).order_by(TextbookPage.page_number))).scalars().all()
        chapter.content = '\n\n'.join(f'[PDF第{p.page_number}页]\n{p.content}' for p in pages)
        chapter.is_published = True
        book.is_published = True
        imported = []
        for figure in sample['figures']:
            if figure['review_status'] != 'extraction_visually_checked_not_published':
                raise ValueError('An unreviewed figure cannot be published')
            width, height = figure['native_pixel_size']
            image = (await db.execute(select(TextbookAsset).where(TextbookAsset.book_id == book.id,
                       TextbookAsset.pdf_page == figure['pdf_page'], TextbookAsset.width == width,
                       TextbookAsset.height == height))).scalars().first()
            if not image:
                raise ValueError(f'No native candidate matches {figure["title"]}')
            original = Path(figure['file']).resolve()
            if not original.is_relative_to(manifest.parent.resolve()):
                raise ValueError('Figure file outside checked sample')
            data = original.read_bytes()
            private_path(image.file_path).write_bytes(data)
            image.sha256 = hashlib.sha256(data).hexdigest()
            image.chapter_id = chapter.id
            image.title = figure['title']
            image.figure_number = figure.get('figure_number') or ''
            image.description = figure['description']
            image.tags_json = json.dumps(figure['tags'], ensure_ascii=False)
            image.conditions = figure['conditions_and_limits']
            image.is_reviewed = True
            imported.append(image.asset_id)
        await db.commit()
        print(json.dumps({'book_id': book.id, 'chapter_id': chapter.id, 'assets': imported,
                          'chapter_text_characters': len(chapter.content)}, ensure_ascii=False))
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.pdf.resolve(), args.manifest.resolve()))
