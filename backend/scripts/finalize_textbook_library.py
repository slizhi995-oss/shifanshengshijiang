"""Finish a newly imported library after corroborating unusual directory layouts.

Only fresh library records from the import report are eligible. Historical
books and chapters referenced by lessons/images are never replaced.
"""
import asyncio
import json
import sqlite3
from pathlib import Path

import fitz
from sqlalchemy import select, func, delete

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookAsset, TextbookLesson
from app.services.textbook_outline import heading_matches
from app.services.textbook_service import private_path
from scripts.import_textbook_library import parse, PARSER_VERSION


async def main():
    output = Path('outputs/textbook-library').resolve()
    report = json.loads((output/'import-report.json').read_text(encoding='utf-8'))
    assert len(report['books']) == report['files'] and not report['errors'], '必须先完成整库导入'
    with sqlite3.connect(Path(report['database_backup']).as_uri()+'?mode=ro', uri=True) as before:
        historical_books = {row[0] for row in before.execute('SELECT id FROM textbooks')}
    unusual = set(json.loads((output/'slash-layout-books.json').read_text(encoding='utf-8')))
    audit = []
    async with async_session_factory() as db:
        for row in report['books']:
            book = await db.get(Textbook, row['book_id'])
            if book.id in historical_books or not book.file_path.startswith('library/'):
                continue
            if row['file'] in unusual:
                old = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id==book.id))).scalars().all()
                old_cache = json.loads((output/'cache'/f"{book.sha256}-v2.json").read_text(encoding='utf-8'))
                fingerprint = lambda item: (item['title'],item['start_page'],item['end_page'],item['content'],bool(item['is_published']))
                current = [dict(title=c.title,start_page=c.start_page,end_page=c.end_page,content=c.content,is_published=c.is_published) for c in old]
                expected = old_cache['chapters']
                source = next(Path(report['source']).rglob(row['file']))
                parsed = await asyncio.to_thread(parse, source, book.sha256, output)
                desired = parsed['chapters']
                if {fingerprint(c) for c in current} != {fingerprint(c) for c in desired}:
                    assert {fingerprint(c) for c in current} == {fingerprint(c) for c in expected}, '导入后章节已修改，不能替换'
                    ids = [c.id for c in old]
                    if ids:
                        for model in (TextbookAsset,TextbookLesson):
                            linked = (await db.execute(select(func.count()).select_from(model).where(model.chapter_id.in_(ids)))).scalar_one()
                            assert linked == 0, '已有图片/教案引用，不能替换'
                        await db.execute(delete(TextbookChapter).where(TextbookChapter.id.in_(ids)))
                    db.add_all(TextbookChapter(book_id=book.id,**chapter) for chapter in desired)
                    await db.commit()
                    audit.append(dict(file=row['file'],replaced_unreferenced_imported_chapters=ids,chapters=len(desired)))
                    row['diagnostics'] = parsed['diagnostics']
            drafts = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id==book.id,TextbookChapter.is_published==False))).scalars().all()
            published = []
            with fitz.open(private_path(book.file_path)) as document:
                for chapter in drafts:
                    page = document[chapter.start_page-1]
                    header = page.get_text(clip=(0,0,page.rect.width,page.rect.height*.48),sort=True)
                    pages = chapter.content.split('\n')
                    actual_text = '\n'.join(line for line in pages if not line.startswith('[PDF第')).strip()
                    if book.status != 'needs_ocr' and 40 <= len(actual_text) and len(chapter.content)<=48000 and heading_matches(chapter.title,header):
                        chapter.is_published = True
                        published.append(chapter.id)
            if published:
                audit.append(dict(file=row['file'],corroborated_draft_chapters=published))
            await db.commit()
            row['chapters'] = (await db.execute(select(func.count()).select_from(TextbookChapter).where(TextbookChapter.book_id==book.id))).scalar_one()
            row['published_chapters'] = (await db.execute(select(func.count()).select_from(TextbookChapter).where(TextbookChapter.book_id==book.id,TextbookChapter.is_published==True))).scalar_one()
            if row['published_chapters'] and book.status != 'needs_ocr':
                book.status = row['status'] = 'ready'
            await db.commit()
    report['finalized_with_parser_version'] = PARSER_VERSION
    (output/'outline-finalization.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    await engine.dispose()
    print(json.dumps(dict(adjustments=len(audit),published_chapters=sum(row['published_chapters'] for row in report['books'])),ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
