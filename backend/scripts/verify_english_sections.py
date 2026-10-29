"""Verify merged directories through student HTTP APIs and export UI fixtures."""
import asyncio
import json
import re
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
from app.services.textbook_english import reviewed_english_directories
from app.services.textbook_junior_english import reviewed_junior_english_directories
from app.services.textbook_english_sections import section_chapters_from_review
from app.services.textbook_service import confirmed_chapter


async def main():
    output = Path('outputs/english-sections')
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
    fixtures, report = [], []
    try:
        async with async_session_factory() as db, httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            books = (await db.execute(select(Textbook).where(Textbook.subject == '英语',
                Textbook.is_published == True).order_by(Textbook.id))).scalars().all()
            for book in books:
                junior = book.grade.startswith('初中')
                review = (reviewed_junior_english_directories() if junior else reviewed_english_directories()).get(book.sha256)
                if not review:
                    continue
                texts = [page.content for page in (await db.execute(select(TextbookPage).where(
                    TextbookPage.book_id == book.id).order_by(TextbookPage.page_number))).scalars()]
                expected = section_chapters_from_review(review, texts, junior)
                response = await client.get(f'/textbooks/{book.id}/chapters')
                assert response.status_code == 200, response.text
                rows = response.json()['data']
                choices = [row for row in rows if not row['is_unit'] and row.get('directory_layout') == 'sections']
                assert [(row['parent_title'], row['title']) for row in choices] == [(row['parent_title'], row['title']) for row in expected]
                for row, source in zip(choices, expected):
                    detail = await client.get(f'/textbooks/chapters/{row["id"]}')
                    assert detail.status_code == 200, detail.text
                    assert detail.json()['data']['content'] == source['content']
                    chapter, _ = await confirmed_chapter(db, row['id'], '英语', book.grade)
                    assert chapter.printed_pages == source['printed_pages']
                    assert len(re.findall(r'\[PDF第\d+页\]', chapter.content)) > 0
                all_books = (await client.get('/textbooks', params=dict(subject='英语',
                    stage='初中' if junior else '高中', catalog_only=True))).json()['data']
                visible = next(row for row in all_books if row['id'] == book.id)
                fixtures.append(dict(book=visible, books=all_books, chapters=rows))
                report.append(dict(book_id=book.id, title=book.title, sections=len(choices),
                    units=len(review['units']), content_and_generation_verified=True))
        (output/'api-fixtures.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding='utf8')
        (output/'api-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
