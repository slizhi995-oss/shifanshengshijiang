"""Add reviewed English topics without replacing historical chapters or references.

Run from backend: python -m scripts.expand_highschool_english [--apply]
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookPage
from app.services.textbook_english import reviewed_english_directories
from app.services.textbook_english_sections import section_chapters_from_review
from app.services.textbook_catalog import is_removed_chapter
from scripts.import_textbook_library import backup_sqlite


async def main(apply=False):
    output = Path('outputs/highschool-english-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, books=[], additions=[], changes=[])
    try:
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).where(Textbook.subject == '英语',
                Textbook.grade.startswith('高中')).order_by(Textbook.id))).scalars().all()
            for book in books:
                if book.sha256 not in reviewed_english_directories():
                    raise ValueError(f'English PDF has no reviewed transcription: {book.id}')
                pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book.id)
                    .order_by(TextbookPage.page_number))).scalars().all()
                if [page.page_number for page in pages] != list(range(1, book.page_count+1)):
                    raise ValueError(f'Incomplete source pages: {book.id}')
                topics = section_chapters_from_review(reviewed_english_directories()[book.sha256], [page.content for page in pages])
                existing = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id))).scalars().all()
                keys = {(row.parent_title, row.title): row for row in existing}
                added = []
                changed = 0
                hidden = 0
                for original in existing:
                    if original.is_published and is_removed_chapter(book.subject, original.title, book.grade):
                        report['changes'].append(dict(id=original.id, field='is_published', before=True, after=False))
                        hidden += 1
                for row in topics:
                    if not row['is_published']:
                        raise ValueError(f'English topic has insufficient source text: {book.id} {row["title"]}')
                    key = (row['parent_title'], row['title'])
                    if key not in keys:
                        added.append(dict(book_id=book.id, **row))
                    else:
                        original = keys[key]
                        for field in ('start_page', 'end_page', 'printed_pages', 'content'):
                            if getattr(original, field) != row[field]:
                                report['changes'].append(dict(id=original.id, field=field,
                                    before=getattr(original, field), after=row[field]))
                                changed += 1
                report['additions'].extend(added)
                report['books'].append(dict(id=book.id, title=book.title, topics=len(topics), added=len(added), changed_fields=changed, removed_appendices=hidden))
            if apply and (report['additions'] or report['changes']):
                report['database_backup'] = backup_sqlite(output)
                recovery = output/f'recovery-{datetime.now():%Y%m%d-%H%M%S-%f}.json'
                recovery.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
                for change in report['changes']:
                    setattr(await db.get(TextbookChapter, change['id']), change['field'], change['after'])
                added_rows = [TextbookChapter(**row) for row in report['additions']]
                db.add_all(added_rows)
                await db.flush()
                report['added_ids'] = [row.id for row in added_rows]
                await db.commit()
            (output/('applied.json' if apply else 'preview.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps({key: value for key, value in report.items() if key not in ('additions', 'changes', 'added_ids')}, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
