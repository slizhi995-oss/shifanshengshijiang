"""Remove primary-Chinese word/stroke tables from the published directory.

From backend: python -m scripts.hide_primary_chinese_supplements [--apply]
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import is_removed_primary_chinese_supplement
from scripts.import_textbook_library import backup_sqlite


async def main(apply=False):
    output = Path('outputs/primary-chinese-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, books=[], changes=[])
    try:
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).where(Textbook.subject == '语文',
                Textbook.grade.startswith('小学')).order_by(Textbook.id))).scalars().all()
            for book in books:
                rows = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id,
                    TextbookChapter.is_published == True))).scalars().all()
                removed = [row for row in rows if is_removed_primary_chinese_supplement(book.subject, row.title, book.grade)]
                report['changes'].extend(dict(id=row.id, field='is_published', before=True, after=False) for row in removed)
                report['books'].append(dict(id=book.id, title=book.title, retained=len(rows)-len(removed),
                    removed=[dict(id=row.id, title=row.title) for row in removed]))
            if apply and report['changes']:
                report['database_backup'] = backup_sqlite(output)
                (output/f'recovery-{datetime.now():%Y%m%d-%H%M%S-%f}.json').write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
                for change in report['changes']:
                    (await db.get(TextbookChapter, change['id'])).is_published = False
                await db.commit()
            (output/('applied.json' if apply else 'preview.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps(dict(applied=apply, books=len(books), removed=len(report['changes']),
                database_backup=report.get('database_backup')), ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
