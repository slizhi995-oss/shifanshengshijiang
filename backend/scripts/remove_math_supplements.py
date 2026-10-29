"""Delete excluded maths directory entries after backing up the database.

Run from backend: python -m scripts.remove_math_supplements [--apply] [--output PATH]
"""
import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import delete, func, select, text

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookAsset, TextbookLesson
from app.services.textbook_catalog import is_removed_math_chapter
from scripts.import_textbook_library import backup_sqlite


async def main(apply=False, output=Path('outputs/math-directory-cleanup')):
    output.mkdir(parents=True, exist_ok=True)
    try:
        async with async_session_factory() as db:
            if engine.url.get_backend_name() == 'sqlite':
                await db.execute(text('PRAGMA foreign_keys=ON'))
            rows = (await db.execute(select(TextbookChapter, Textbook).join(
                Textbook, TextbookChapter.book_id == Textbook.id).where(Textbook.subject == '数学'))).all()
            removed = [(chapter, book) for chapter, book in rows
                       if is_removed_math_chapter(book.subject, chapter.title)]
            ids = [chapter.id for chapter, _ in removed]
            report = {'applied': apply, 'count': len(ids), 'books': dict(Counter(book.id for _, book in removed)),
                      'removed': [{column.name: getattr(chapter, column.name) for column in chapter.__table__.columns}
                                  for chapter, _ in removed]}
            for model in (TextbookAsset, TextbookLesson):
                references = (await db.execute(select(func.count()).select_from(model).where(model.chapter_id.in_(ids)))).scalar_one()
                if references:
                    raise RuntimeError(f'{model.__tablename__}: {references} references require preservation before deletion')
            if apply and ids:
                report['database_backup'] = backup_sqlite(output)
                # Write the recovery report before the destructive transaction.
                (output / 'removed-chapters.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
                await db.execute(delete(TextbookChapter).where(TextbookChapter.id.in_(ids)))
                await db.commit()
            (output / ('applied.json' if apply else 'preview.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            print(json.dumps({key: value for key, value in report.items() if key != 'removed'}, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('outputs/math-directory-cleanup'))
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.output))
