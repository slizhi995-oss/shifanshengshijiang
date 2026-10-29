"""Merge reviewed secondary English tasks into selectable sections.

From backend: python -m scripts.merge_english_sections [--apply]
The preview rolls back; apply creates a full SQLite backup before one transaction.
Historical chapter IDs, lessons and image bindings are retained.
"""
import argparse
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookPage
from app.services.textbook_english import reviewed_english_directories, _unit_key as highschool_unit_key
from app.services.textbook_junior_english import reviewed_junior_english_directories, _unit_key as junior_unit_key
from app.services.textbook_english_sections import section_chapters_from_review
from app.services.textbook_units import group_chapter_directory
from scripts.import_textbook_library import backup_sqlite


async def synchronize(db, stage=''):
    report = dict(books=[], added=0, hidden=0, updated_fields=0)
    books = (await db.execute(select(Textbook).where(Textbook.subject == '英语',
        Textbook.is_published == True).order_by(Textbook.id))).scalars().all()
    for book in books:
        junior = book.grade.startswith('初中')
        if not junior and not book.grade.startswith('高中'):
            continue
        if stage and not book.grade.startswith(stage):
            continue
        review = (reviewed_junior_english_directories() if junior else reviewed_english_directories()).get(book.sha256)
        if not review:
            continue  # Other uploaded editions have no hash-bound source review.
        pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book.id)
                                 .order_by(TextbookPage.page_number))).scalars().all()
        if [page.page_number for page in pages] != list(range(1, book.page_count + 1)):
            raise ValueError(f'Incomplete source pages: {book.id}')
        sections = section_chapters_from_review(review, [page.content for page in pages], junior)
        if any(not row['is_published'] or max(len(row['title']), len(row['parent_title'])) > 160 for row in sections):
            raise ValueError(f'Invalid section label or source text: {book.id}')
        existing = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id))).scalars().all()
        keys = {}
        for row in existing:
            key = (row.parent_title, row.title)
            if key in keys:
                raise ValueError(f'Duplicate chapter key: {book.id}: {key}')
            keys[key] = row
        added, hidden, updated = 0, 0, 0
        allowed = set()
        for values in sections:
            original = keys.get((values['parent_title'], values['title']))
            if original is None:
                original = TextbookChapter(book_id=book.id, **values)
                db.add(original)
                added += 1
            else:
                for field, value in values.items():
                    if getattr(original, field) != value:
                        setattr(original, field, value)
                        updated += 1
            allowed.add((values['parent_title'], values['title']))
        unit_key = junior_unit_key if junior else highschool_unit_key
        units = {unit_key(unit['title']) for unit in review['units']}
        for row in existing:
            keep = (row.parent_title, row.title) in allowed or (not row.parent_title and
                (unit_key(row.title) in units or (not junior and re.fullmatch(r'Workbook\s+Unit\s*\d+', row.title, re.I))))
            if row.is_published and not keep:
                row.is_published = False
                hidden += 1
        await db.flush()
        published = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id,
            TextbookChapter.is_published == True).order_by(TextbookChapter.start_page, TextbookChapter.id))).scalars().all()
        directory = group_chapter_directory(book, [dict(id=row.id, title=row.title, parent_title=row.parent_title,
            start_page=row.start_page, end_page=row.end_page, printed_pages=row.printed_pages,
            is_published=row.is_published, book_id=book.id) for row in published])
        visible = [row for row in directory if not row['is_unit'] and row.get('directory_layout') == 'sections']
        if len(visible) != len(sections):
            raise ValueError(f'Incomplete merged directory: {book.id}')
        report['books'].append(dict(id=book.id, title=book.title, grade=book.grade,
            sections=len(sections), added=added, hidden=hidden, updated_fields=updated))
        report['added'] += added
        report['hidden'] += hidden
        report['updated_fields'] += updated
    return report


async def main(apply=False, stage=''):
    output = Path('outputs/english-sections')
    output.mkdir(parents=True, exist_ok=True)
    try:
        backup = backup_sqlite(output) if apply else None
        async with async_session_factory() as db:
            report = await synchronize(db, stage)
            if apply:
                await db.commit()
            else:
                await db.rollback()
        report.update(applied=apply, database_backup=backup)
        path = output / f'{"applied" if apply else "preview"}-{datetime.now():%Y%m%d-%H%M%S-%f}.json'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--stage', choices=('初中', '高中'), default='')
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.stage))
