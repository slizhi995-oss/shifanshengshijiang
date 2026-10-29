"""Unpublish supplements in the five reviewed primary-English flat directories.

From backend: python -m scripts.flatten_primary_english [--apply]
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_primary_english import (
    FLAT_PRIMARY_ENGLISH_DIGESTS, primary_english_chapter_allowed, reviewed_flat_primary_english_directory,
)
from scripts.import_textbook_library import backup_sqlite


async def main(apply=False):
    output = Path('outputs/primary-english-flat-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, books=[], changes=[])
    try:
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).where(Textbook.subject == '英语',
                Textbook.grade.startswith('小学'), Textbook.sha256.in_(FLAT_PRIMARY_ENGLISH_DIGESTS))
                .order_by(Textbook.id))).scalars().all()
            for book in books:
                chapters = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id))).scalars().all()
                review = reviewed_flat_primary_english_directory(book.sha256)
                expected = {entry['title'] for entry in review['entries']}
                retained = [row for row in chapters if row.is_published and row.title in expected]
                if len(retained) != len(expected) or {row.title for row in retained} != expected:
                    raise ValueError(f'Incomplete or duplicate published teaching entries: {book.id}')
                removed = [row for row in chapters if row.is_published
                    and primary_english_chapter_allowed(book.sha256, row.title) is False]
                report['changes'].extend(dict(id=row.id, field='is_published', before=True, after=False) for row in removed)
                report['books'].append(dict(id=book.id, title=book.title, retained=len(retained), removed=len(removed)))
            if apply and report['changes']:
                report['database_backup'] = backup_sqlite(output)
                (output/f'recovery-{datetime.now():%Y%m%d-%H%M%S-%f}.json').write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
                for change in report['changes']:
                    (await db.get(TextbookChapter, change['id'])).is_published = False
                await db.commit()
            (output/('applied.json' if apply else 'preview.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps({key: value for key, value in report.items() if key != 'changes'}, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
