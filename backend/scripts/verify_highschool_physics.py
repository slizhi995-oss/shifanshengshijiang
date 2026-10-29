"""Check the persisted cleanup and export API responses for the browser checks."""
import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from app.api.routes.textbooks import book_data, list_chapters
from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook
from app.models.user import UserRole
from app.services.textbook_catalog import is_removed_chapter


async def main():
    output = Path('outputs/highschool-physics-directory')
    report = json.loads((output/'applied.json').read_text(encoding='utf-8'))
    allowed = {(c['id'], c['field']) for c in report['changes']}
    removed = {row['id'] for row in report['removed']}
    with sqlite3.connect(report['database_backup']) as before, sqlite3.connect(engine.url.database) as after:
        before.row_factory = after.row_factory = sqlite3.Row
        old = {row['id']: dict(row) for row in before.execute('select * from textbook_chapters')}
        current = {row['id']: dict(row) for row in after.execute('select * from textbook_chapters')}
        assert old.keys() - removed == current.keys()
        for identifier, row in current.items():
            for field, value in row.items():
                if field != 'updated_at' and (identifier, field) not in allowed:
                    assert old[identifier][field] == value, (identifier, field)
        for table in ('textbooks', 'textbook_pages', 'textbook_assets', 'textbook_lessons'):
            assert before.execute(f'select * from {table} order by id').fetchall() == after.execute(
                f'select * from {table} order by id').fetchall(), table
    try:
        fixtures = []
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).where(Textbook.subject == '物理',
                Textbook.grade.startswith('高中')).order_by(Textbook.id))).scalars().all()
            for book in books:
                rows = (await list_chapters(book.id, db=db, user=SimpleNamespace(role=UserRole.STUDENT)))['data']
                assert rows and rows[0]['is_unit']
                for row in rows:
                    assert not is_removed_chapter(book.subject, row['title'], book.grade)
                    if row['is_unit']:
                        assert not row['is_nested'] and not row['parent_title']
                        assert row['title'] == row['unit_title']
                    else:
                        assert row['is_nested'] and row['parent_title'] == row['unit_title']
                fixtures.append(dict(book=book_data(book), chapters=rows))
                print(f'{book.id} {book.title}: {len(rows)} directory rows verified')
        (output/'catalog.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding='utf-8')
        print('All remaining chapter IDs, contents, ranges, source pages, images and existing lessons preserved.')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
