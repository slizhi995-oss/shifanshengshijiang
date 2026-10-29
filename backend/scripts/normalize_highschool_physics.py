"""Remove nonchapter resources and persist high-school physics chapter parents.

Run from backend: python -m scripts.normalize_highschool_physics [--apply]
SQLite is backed up before writes; source pages, lessons and images are preserved.
"""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import delete, func, select, text

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookAsset, TextbookLesson
from app.services.textbook_physics import stored_physics_directory
from scripts.import_textbook_library import backup_sqlite


def proposals(book, chapters):
    raw = [{column.name: getattr(chapter, column.name) for column in chapter.__table__.columns}
           for chapter in chapters]
    directory = stored_physics_directory(book, raw)
    retained = {row['id'] for row in directory}
    by_id = {row['id']: row for row in raw}
    changes = [dict(id=row['id'], field=field, before=by_id[row['id']][field], after=row[field])
               for row in directory for field in ('title', 'parent_title')
               if by_id[row['id']][field] != row[field]]
    return changes, [row for row in raw if row['id'] not in retained]


async def main(apply=False):
    output = Path('outputs/highschool-physics-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, changes=[], removed=[], books=[])
    try:
        async with async_session_factory() as db:
            if engine.url.get_backend_name() == 'sqlite':
                await db.execute(text('PRAGMA foreign_keys=ON'))
            books = (await db.execute(select(Textbook).where(Textbook.subject == '物理',
                Textbook.grade.startswith('高中')).order_by(Textbook.id))).scalars().all()
            by_id = {}
            for book in books:
                chapters = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id)
                    .order_by(TextbookChapter.start_page, TextbookChapter.id))).scalars().all()
                by_id.update({c.id: c for c in chapters})
                changes, removed = proposals(book, chapters)
                report['changes'].extend(changes)
                report['removed'].extend(removed)
                report['books'].append(book.id)
            ids = [row['id'] for row in report['removed']]
            for model in (TextbookAsset, TextbookLesson):
                count = (await db.execute(select(func.count()).select_from(model).where(model.chapter_id.in_(ids)))).scalar_one()
                if count:
                    raise RuntimeError(f'{model.__tablename__}: preserve {count} references before deletion')
            if apply and (ids or report['changes']):
                report['database_backup'] = backup_sqlite(output)
                (output/'recovery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
                for change in report['changes']:
                    setattr(by_id[change['id']], change['field'], change['after'])
                if ids:
                    await db.execute(delete(TextbookChapter).where(TextbookChapter.id.in_(ids)))
                await db.commit()
            target = 'applied.json' if apply and (ids or report['changes']) else 'preview.json'
            (output/target).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            print(json.dumps(dict(applied=apply, books=len(books), removed=len(ids), changes=len(report['changes']),
                                  database_backup=report.get('database_backup')), ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
