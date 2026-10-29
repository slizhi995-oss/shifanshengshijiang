"""Unpublish excluded junior chemistry directory entries without deleting history.

Run from backend: python -m scripts.hide_junior_chemistry_supplements [--apply]
"""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import is_removed_junior_chemistry
from scripts.import_textbook_library import backup_sqlite


async def main(apply=False):
    output = Path('outputs/junior-chemistry-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, changes=[])
    try:
        async with async_session_factory() as db:
            pairs = (await db.execute(select(TextbookChapter, Textbook).join(Textbook)
                     .where(Textbook.subject == '化学', Textbook.grade.startswith('初中')))).all()
            hidden = [(chapter, book) for chapter, book in pairs if chapter.is_published
                      and is_removed_junior_chemistry(book.subject, chapter.title, book.grade)]
            report['changes'] = [dict(id=chapter.id, book_id=book.id, title=chapter.title,
                                      before=True, after=False) for chapter, book in hidden]
            if apply and hidden:
                report['database_backup'] = backup_sqlite(output)
                (output/'recovery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
                for chapter, _ in hidden:
                    chapter.is_published = False
                await db.commit()
            target = 'applied.json' if apply and hidden else 'preview.json'
            (output/target).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps(dict(applied=apply, hidden=len(hidden),
                                  books=sorted({book.id for _, book in hidden}),
                                  database_backup=report.get('database_backup')), ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
