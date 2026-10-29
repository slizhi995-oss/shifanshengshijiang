"""Check restored directory labels, preserved material bindings and student API."""
import asyncio
import json
import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from app.api.routes import textbooks
from app.core.database import async_session_factory, engine, get_db
from app.core.deps import get_current_user
from app.models.user import UserRole
from app.services.textbook_outline import reviewed_directory, title_key


async def main():
    report = json.loads(Path('outputs/chapter-numbering/applied.json').read_text(encoding='utf8'))
    before = sqlite3.connect(report['database_backup'])
    current = sqlite3.connect('app.db')
    for table in ('textbook_assets', 'textbook_lessons'):
        assert current.execute(f'SELECT * FROM {table} ORDER BY id').fetchall() == before.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
    columns = 'id,book_id,start_page,end_page,printed_pages,content'
    assert current.execute(f'SELECT {columns} FROM textbook_chapters ORDER BY id').fetchall() == before.execute(f'SELECT {columns} FROM textbook_chapters ORDER BY id').fetchall()
    assert not current.execute('PRAGMA foreign_key_check').fetchall()
    app = FastAPI()
    app.include_router(textbooks.router, prefix='/textbooks')
    async def database():
        async with async_session_factory() as db:
            yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=0, role=UserRole.STUDENT)
    fixtures = []
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://catalog') as client:
            books = (await client.get('/textbooks')).json()['data']
            rows_by_book = {}
            entries_checked = 0
            for book in books:
                response = await client.get(f'/textbooks/{book["id"]}/chapters')
                assert response.status_code == 200
                rows = response.json()['data']
                assert not any(re.match(r'^\d+\.\s', row['title']) for row in rows)
                digest = current.execute('SELECT sha256 FROM textbooks WHERE id=?',(book['id'],)).fetchone()[0]
                directory = reviewed_directory(digest)
                if directory:
                    keys = {(row['start_page'],title_key(row['title'])) for row in rows}
                    missing = [entry for entry in directory['entries'] if
                               (entry['printed']+directory['offset'],title_key(entry['title'])) not in keys]
                    assert not missing, (book['id'],missing)
                    entries_checked += len(directory['entries'])
                rows_by_book[book['id']] = rows
                if book['id'] in (111, 15, 106, 4):
                    fixtures.append(dict(book=book, chapters=rows))
            example = rows_by_book[111]
            for unit, expected in [
                ('第二单元·汉语拼音', [('1 a o e','20'),('2 i u ü','22'),('3 b p m f','24'),('4 d t n l','26'),('◎ 语文园地二','28')]),
                ('第三单元·汉语拼音', [('5 g k h','32'),('6 j q x','34'),('7 z c s','36'),('8 zh ch sh r','38'),('9 y w','40'),('◎ 语文园地三','42')]),
            ]:
                actual = [(row['title'],row['printed_pages']) for row in example if row['unit_title'] == unit and not row['is_unit']]
                assert actual == expected, (unit, actual)
            hidden = {change['id'] for change in report['hide']}
            assert not hidden & {row['id'] for rows in rows_by_book.values() for row in rows}
        output = Path('outputs/unit-groups')
        output.mkdir(exist_ok=True)
        (output/'catalog.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding='utf8')
        result = dict(passed=True, books=len(books), directory_entries_checked=entries_checked, student_directory_rows=sum(map(len,rows_by_book.values())),
                      example_matches_printed_directory=True, ids_ranges_content_images_lessons_preserved=True,
                      duplicates_unpublished=len(hidden))
        (output/'strict-directory-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(result, ensure_ascii=False))
    finally:
        before.close()
        current.close()
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
