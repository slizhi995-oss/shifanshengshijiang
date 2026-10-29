"""Check synchronized English PDFs and real student HTTP responses; export UI fixtures."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from app.api.routes import textbooks
from app.core.database import async_session_factory, engine, get_db
from app.core.deps import get_current_user
from app.models.textbook import Textbook, TextbookPage
from app.models.user import UserRole
from app.services.textbook_service import confirmed_chapter, private_path
from scripts.import_textbook_library import digest
from scripts.sync_updated_english import MANIFEST_PATH


async def main():
    output = Path('outputs/english-refresh-20261021')
    output.mkdir(parents=True, exist_ok=True)
    app = FastAPI()
    app.include_router(textbooks.router, prefix='/textbooks')

    async def database():
        async with async_session_factory() as db:
            yield db

    async def student():
        return SimpleNamespace(id=1, role=UserRole.STUDENT)

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = student
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf8'))
    report, fixtures = [], []
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            for item in manifest:
                async with async_session_factory() as db:
                    book = (await db.execute(select(Textbook).where(Textbook.sha256 == item['sha256']))).scalar_one()
                    old = (await db.execute(select(Textbook).where(Textbook.sha256 == item['replaces']))).scalar_one()
                    assert book.is_published and not old.is_published
                    assert digest(private_path(book.file_path)) == book.sha256
                    source_pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book.id)
                        .order_by(TextbookPage.page_number))).scalars().all()
                    assert [row.page_number for row in source_pages] == list(range(1, book.page_count+1))
                    texts = [row.content for row in source_pages]
                    stage = '小学' if book.grade.startswith('小学') else '初中'
                    response = await client.get('/textbooks', params=dict(subject='英语', stage=stage, catalog_only=True))
                    assert response.status_code == 200, response.text
                    books = response.json()['data']
                    assert len([row for row in books if row['title'] == book.title]) == 1
                    assert old.id not in {row['id'] for row in books}
                    assert not any(row['title'] == '九年级全一册' for row in books)
                    response = await client.get(f'/textbooks/{book.id}/chapters')
                    assert response.status_code == 200, response.text
                    rows = response.json()['data']
                    assert len(rows) == item['chapters']
                    for row in rows:
                        detail = await client.get(f'/textbooks/chapters/{row["id"]}')
                        assert detail.status_code == 200, detail.text
                        detail = detail.json()['data']
                        expected = '\n\n'.join(f'[PDF第{number}页]\n{texts[number-1]}'
                            for number in range(row['start_page'], row['end_page']+1))
                        assert detail['content'] == expected
                        if not row['is_unit']:
                            await confirmed_chapter(db, row['id'], '英语', book.grade)
                    assert (await client.get(f'/textbooks/{old.id}/chapters')).status_code == 404
                    assert (await client.get('/textbooks/recommend', params=dict(subject='英语', grade=stage,
                        book_id=old.id))).json()['data'] == []
                    visible_book = next(row for row in books if row['id'] == book.id)
                    fixtures.append(dict(book=visible_book, books=books, chapters=rows))
                    report.append(dict(book_id=book.id, title=book.title, old_book_id=old.id, pages=book.page_count,
                        directory_rows=len(rows), selectable=sum(not row['is_unit'] for row in rows),
                        pdf_hash_verified=True, all_source_ranges_verified=True, old_edition_hidden=True))
        (output/'api-fixtures.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        (output/'api-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
