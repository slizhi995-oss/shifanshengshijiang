"""Persist the audited plain physics directory, retaining IDs and all content.

Run from backend: python -m scripts.normalize_junior_physics [--apply]
The default writes a preview. Applying backs up SQLite before metadata changes.
"""
import argparse
import asyncio
import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_outline import reviewed_directory, title_key
from app.services.textbook_catalog import is_removed_physics_appendix
from app.services.textbook_physics import physics_directory
from app.services.textbook_service import private_path
from scripts.import_textbook_library import backup_sqlite


def proposals(book, chapters):
    review = reviewed_directory(book.sha256)
    if not review:
        raise ValueError(f'No audited directory for book {book.id}')
    used, changes, hidden = set(), [], []
    rows = physics_directory([dict(title=e['title'], start_page=e['printed']+review['offset'])
                              for e in review['entries'] if not is_removed_physics_appendix('物理', e['title'])])
    chapters = [c for c in chapters if not is_removed_physics_appendix('物理', c.title)]
    if len({row['start_page'] for row in rows}) != len(rows):
        raise ValueError('Shared directory pages require individual review')
    for row in rows:
        candidates = [c for c in chapters if c.start_page == row['start_page']]
        if not candidates:
            raise ValueError(f'Missing chapter: {row["title"]}')
        # Prefer a matching full label, then the original named row over a bare marker.
        candidates.sort(key=lambda c: (c.title != row['title'],
                                       title_key(c.title) != title_key(row['title']), c.id))
        chapter = candidates[0]
        used.add(chapter.id)
        for field in ('title', 'parent_title'):
            if getattr(chapter, field) != row[field]:
                changes.append(dict(id=chapter.id, field=field, before=getattr(chapter, field), after=row[field]))
        for duplicate in candidates[1:]:
            if not (re.fullmatch(r'第\s*[\d一二三四五六七八九十百零〇]+\s*章', duplicate.title)
                    or title_key(duplicate.title) == title_key(row['title'])):
                raise ValueError(f'Unexpected entry on the same page: {duplicate.title}')
            used.add(duplicate.id)
            if duplicate.is_published:
                hidden.append(duplicate.id)
    if used != {c.id for c in chapters}:
        raise ValueError('Unexpected rows outside the audited directory; review before applying')
    return changes, hidden


async def main(apply=False):
    output = Path('outputs/junior-physics-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, changes=[], hidden_duplicates=[])
    try:
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).where(
                Textbook.subject == '物理', Textbook.grade.startswith('初中')).order_by(Textbook.id))).scalars().all()
            all_chapters = {}
            for book in books:
                source = private_path(book.file_path)
                if hashlib.sha256(source.read_bytes()).hexdigest() != book.sha256:
                    raise ValueError('Original PDF digest changed')
                chapters = (await db.execute(select(TextbookChapter).where(
                    TextbookChapter.book_id == book.id).order_by(TextbookChapter.start_page, TextbookChapter.id))).scalars().all()
                all_chapters.update({c.id: c for c in chapters})
                changes, hidden = proposals(book, chapters)
                report['changes'].extend(changes)
                report['hidden_duplicates'].extend(hidden)
            if apply and (report['changes'] or report['hidden_duplicates']):
                report['database_backup'] = backup_sqlite(output)
                for change in report['changes']:
                    setattr(all_chapters[change['id']], change['field'], change['after'])
                for identifier in report['hidden_duplicates']:
                    all_chapters[identifier].is_published = False
                await db.commit()
            report['books'] = len(books)
            (output / ('applied.json' if apply else 'preview.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(dict(books=len(books), changes=len(report['changes']),
                                  hidden_duplicates=len(report['hidden_duplicates']), applied=apply,
                                  database_backup=report.get('database_backup')), ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
