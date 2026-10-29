"""Read-only checks against an applied library report and its SQLite backup."""
import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from app.api.routes import textbooks
from app.core.database import async_session_factory, engine, get_db
from app.core.deps import get_current_user
from app.models.textbook import Textbook
from app.models.user import UserRole
from app.services.textbook_catalog import SUBJECTS, STAGES, filename_metadata
from app.services.textbook_service import confirmed_chapter, private_path
from scripts.import_textbook_library import digest


async def main():
    output = Path('outputs/textbook-library')
    report = json.loads((output/'import-report.json').read_text(encoding='utf-8'))
    assert not report['errors'] and len(report['books']) == report['files']
    source = Path(report['source'])
    files = {path.name: path for path in source.rglob('*.pdf')}
    assert len(files) == len(report['books'])
    db_path = Path(engine.url.database).resolve()
    counts = {}
    with sqlite3.connect(db_path.as_uri()+'?mode=ro', uri=True) as db:
        for row in report['books']:
            book = db.execute('SELECT sha256,file_path,page_count,original_filename,title,subject,grade FROM textbooks WHERE id=?', (row['book_id'],)).fetchone()
            assert book and book[0] == digest(files[row['file']]) == row['sha256']
            assert digest(private_path(book[1])) == book[0]
            assert book[2] == row['pages']
            assert book[3] == row['file']
            assert book[4] == filename_metadata(row['file'])['title']
            page_count = db.execute('SELECT count(*) FROM textbook_pages WHERE book_id=?', (row['book_id'],)).fetchone()[0]
            assert page_count == row['pages']
            chapters = db.execute('SELECT title,start_page,end_page,content,is_published FROM textbook_chapters WHERE book_id=?', (row['book_id'],)).fetchall()
            for title, start, end, content, published in chapters:
                assert 1 <= start <= end <= row['pages']
                if published:
                    assert 0 < len(content) <= 48000
            for table in ('textbooks','textbook_pages','textbook_chapters','textbook_assets','textbook_lessons'):
                counts[table] = db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
        # All historical chapter, image and lesson rows must remain byte-for-byte
        # equal, including their IDs and references.
        with sqlite3.connect(Path(report['database_backup']).as_uri()+'?mode=ro', uri=True) as before:
            preserved = {}
            for table in ('textbook_chapters','textbook_assets','textbook_lessons'):
                cursor = before.execute(f'SELECT * FROM {table}')
                id_index = [column[0] for column in cursor.description].index('id')
                original = cursor.fetchall()
                for row in original:
                    assert db.execute(f'SELECT * FROM {table} WHERE id=?', (row[id_index],)).fetchone() == row
                preserved[table] = len(original)
    app = FastAPI()
    app.include_router(textbooks.router, prefix='/textbooks')
    async def database():
        async with async_session_factory() as db:
            yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=0, role=UserRole.STUDENT)
    selections = []
    current_chapter_counts = {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://library') as client:
        listed = (await client.get('/textbooks', params={'catalog_only': True})).json()['data']
        assert {book['id'] for book in listed} == {row['book_id'] for row in report['books']}
        for subject in SUBJECTS:
            for stage in STAGES:
                books = (await client.get('/textbooks', params={'subject':subject, 'stage':stage, 'catalog_only':True})).json()['data']
                expected = [book for book in listed if book['subject']==subject and book['stage']==stage]
                assert {book['id'] for book in books} == {book['id'] for book in expected}
                selections.append(dict(subject=subject, stage=stage, books=len(books)))
        for book in listed:
            chapters = (await client.get(f"/textbooks/{book['id']}/chapters")).json()['data']
            current_chapter_counts[book['id']] = len(chapters)
            if chapters:
                chapter = chapters[0]
                async with async_session_factory() as db:
                    verified, _ = await confirmed_chapter(db, chapter['id'], book['subject'], book['stage'])
                    assert verified.id == chapter['id']
                recommended = (await client.get('/textbooks/recommend', params=dict(
                    subject=book['subject'],grade=book['stage'],book_id=book['id'],topic=chapter['title']))).json()['data']
                assert any(item['id']==chapter['id'] for item in recommended)
    summary = dict(passed=True, source_books=len(files), source_pages=sum(row['pages'] for row in report['books']),
                   published_chapters=sum(current_chapter_counts.values()),
                   database_counts=counts, historical_rows_preserved=preserved, selections=selections,
                   needs_attention=[dict(file=book['original_filename'],status=book['status']) for book in listed if not current_chapter_counts[book['id']]])
    (output/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in summary.items() if key!='selections'},ensure_ascii=False))
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
