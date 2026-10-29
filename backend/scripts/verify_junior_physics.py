"""Verify persisted directories and export actual API data for browser checks."""
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
from app.services.textbook_outline import reviewed_directory
from app.services.textbook_physics import SECTION
from app.services.textbook_catalog import is_removed_chapter


async def main():
    output = Path('outputs/junior-physics-directory')
    report = json.loads((output/'applied.json').read_text(encoding='utf-8'))
    allowed = {(c['id'], c['field']) for c in report['changes']}
    allowed.update((identifier, 'is_published') for identifier in report['hidden_duplicates'])
    highschool_path = Path('outputs/highschool-physics-directory/applied.json')
    highschool = json.loads(highschool_path.read_text(encoding='utf-8')) if highschool_path.exists() else {}
    allowed.update((c['id'], c['field']) for c in highschool.get('changes', []))
    # Check every stored chapter, including other subjects, against the backup.
    with sqlite3.connect(report['database_backup']) as before, sqlite3.connect(engine.url.database) as after:
        before.row_factory = after.row_factory = sqlite3.Row
        previous = {row['id']: dict(row) for row in before.execute('select * from textbook_chapters')}
        current = {row['id']: dict(row) for row in after.execute('select * from textbook_chapters')}
        removals = Path('outputs/physics-appendix-cleanup/applied.json')
        deleted = {r['id'] for r in json.loads(removals.read_text(encoding='utf-8'))['removed']} if removals.exists() else set()
        deleted.update(r['id'] for r in highschool.get('removed', []))
        assert previous.keys() - deleted == current.keys()
        for identifier, row in previous.items():
            if identifier in deleted:
                continue
            for key, value in row.items():
                if key != 'updated_at' and (identifier, key) not in allowed:
                    assert current[identifier][key] == value, (identifier, key)
        for table in ('textbook_pages', 'textbook_assets', 'textbook_lessons'):
            assert before.execute(f'select * from {table} order by id').fetchall() == after.execute(
                f'select * from {table} order by id').fetchall(), table
    fixtures = []
    try:
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).where(
                Textbook.subject == '物理', Textbook.grade.startswith('初中')).order_by(Textbook.id))).scalars().all()
            for book in books:
                rows = (await list_chapters(book.id, db=db, user=SimpleNamespace(role=UserRole.STUDENT)))['data']
                review = reviewed_directory(book.sha256)
                assert [row['title'] for row in rows] == [e['title'] for e in review['entries']
                                                        if not is_removed_chapter(book.subject, e['title'])]
                assert len({(row['start_page'], row['title']) for row in rows}) == len(rows)
                for row in rows:
                    assert row['is_nested'] == (bool(SECTION.match(row['title'])) or row['title'].strip() == '整理与复习')
                    if not row['is_unit'] and not row['title'].startswith(('走进', '附录')):
                        assert row['parent_title'] == row['unit_title'] and row['parent_title']
                fixtures.append(dict(book=book_data(book), chapters=rows))
                print(f'{book.title}: {len(rows)} rows verified')
        (output/'catalog.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding='utf-8')
        print('All chapter IDs, page ranges, text, images and existing lessons preserved.')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
