"""Expand only the reviewed grade 7–9 English books; preserve historical IDs.

From backend: python -m scripts.expand_junior_english [--apply]
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookPage
from app.services.textbook_junior_english import reviewed_junior_english_directories
from app.services.textbook_english_sections import section_chapters_from_review
from app.services.textbook_catalog import is_removed_chapter
from scripts.import_textbook_library import backup_sqlite


async def main(apply=False):
    output = Path('outputs/junior-english-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, books=[], additions=[], changes=[])
    try:
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).where(Textbook.subject == '英语',
                Textbook.grade.startswith('初中'), Textbook.sha256.in_(reviewed_junior_english_directories()))
                .order_by(Textbook.id))).scalars().all()
            for book in books:
                pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book.id)
                    .order_by(TextbookPage.page_number))).scalars().all()
                if [page.page_number for page in pages] != list(range(1, book.page_count+1)):
                    raise ValueError(f'Incomplete source pages: {book.id}')
                topics = section_chapters_from_review(reviewed_junior_english_directories()[book.sha256], [page.content for page in pages], junior=True)
                existing = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id))).scalars().all()
                keys = {(row.parent_title, row.title): row for row in existing}
                added, changed, removed = [], 0, 0
                for original in existing:
                    if original.is_published and is_removed_chapter(book.subject, original.title, book.grade, book.sha256):
                        report['changes'].append(dict(id=original.id, field='is_published', before=True, after=False))
                        removed += 1
                for row in topics:
                    if not row['is_published'] or max(len(row['title']), len(row['parent_title'])) > 160:
                        raise ValueError(f'English topic has invalid label or source text: {book.id} {row["title"]}')
                    original = keys.get((row['parent_title'], row['title']))
                    if original is None:
                        added.append(dict(book_id=book.id, **row))
                    else:
                        for field in ('start_page', 'end_page', 'printed_pages', 'content'):
                            if getattr(original, field) != row[field]:
                                report['changes'].append(dict(id=original.id, field=field,
                                    before=getattr(original, field), after=row[field]))
                                changed += 1
                report['additions'].extend(added)
                report['books'].append(dict(id=book.id, title=book.title, topics=len(topics), added=len(added), changed_fields=changed, removed_supplements=removed))
            if apply and (report['additions'] or report['changes']):
                report['database_backup'] = backup_sqlite(output)
                recovery = output/f'recovery-{datetime.now():%Y%m%d-%H%M%S-%f}.json'
                recovery.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
                for change in report['changes']:
                    setattr(await db.get(TextbookChapter, change['id']), change['field'], change['after'])
                additions = [TextbookChapter(**row) for row in report['additions']]
                db.add_all(additions)
                await db.flush()
                report['added_ids'] = [row.id for row in additions]
                await db.commit()
            (output/('applied.json' if apply else 'preview.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps({key: value for key, value in report.items()
                if key not in ('additions', 'changes', 'added_ids')}, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
