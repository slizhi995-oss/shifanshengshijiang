"""Verify every audited directory entry through the student chapter endpoint."""
import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import httpx
from fastapi import FastAPI
from app.api.routes import textbooks
from app.core.database import async_session_factory,engine,get_db
from app.core.deps import get_current_user
from app.models.user import UserRole
from app.services.textbook_outline import title_key
from app.services.textbook_service import confirmed_chapter

ROOT=Path('outputs/catalog-completeness')


async def main():
    original=json.loads((ROOT/'initial-applied.json').read_text(encoding='utf-8'))
    audit=json.loads((ROOT/'audit.json').read_text(encoding='utf-8'))
    current=sqlite3.connect('app.db')
    before=sqlite3.connect(original['database_backup'])
    for table in ('textbook_assets','textbook_lessons'):
        assert current.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()==before.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
    original_ids={r[0] for r in before.execute('SELECT id FROM textbook_chapters')}
    assert original_ids<={r[0] for r in current.execute('SELECT id FROM textbook_chapters')}
    for identifier,title,parent in before.execute("SELECT id,title,parent_title FROM textbook_chapters WHERE title LIKE '%*%' OR parent_title LIKE '%*%'"):
        row=current.execute('SELECT title,parent_title FROM textbook_chapters WHERE id=?',(identifier,)).fetchone()
        assert row[0].count('*')>=title.count('*') and row[1].count('*')>=parent.count('*')
    assert not current.execute('PRAGMA foreign_key_check').fetchall()
    app=FastAPI()
    app.include_router(textbooks.router,prefix='/textbooks')
    async def database():
        async with async_session_factory() as db:yield db
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id=0,role=UserRole.STUDENT)
    checked=0
    counts=[]
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://catalog') as client:
            for book in audit:
                response=await client.get(f'/textbooks/{book["id"]}/chapters')
                assert response.status_code==200
                rows=response.json()['data']
                keys={(c['start_page'],title_key(c['title'])) for c in rows}
                missing=[e for e in book['entries'] if (e['start'],title_key(e['title'])) not in keys]
                assert not missing,(book['file'],missing)
                for chapter in rows:
                    start,end,content=current.execute('SELECT start_page,end_page,content FROM textbook_chapters WHERE id=?',(chapter['id'],)).fetchone()
                    assert 1<=start<=end<=book['pages'] and 40<=len(content)<=48000
                    assert not chapter['title'].lstrip().startswith(('.', '．','·','…'))
                async with async_session_factory() as db:
                    for chapter in (rows[0],rows[-1]):
                        confirmed,_=await confirmed_chapter(db,chapter['id'],book['subject'] if 'subject' in book else current.execute('SELECT subject FROM textbooks WHERE id=?',(book['id'],)).fetchone()[0],
                            current.execute('SELECT grade FROM textbooks WHERE id=?',(book['id'],)).fetchone()[0])
                        assert confirmed.id==chapter['id']
                checked+=len(book['entries'])
                counts.append(dict(id=book['id'],file=book['file'],directory_entries=len(book['entries']),visible_chapters=len(rows)))
        published=sum(b['visible_chapters'] for b in counts)
        added=current.execute('SELECT count(*) FROM textbook_chapters').fetchone()[0]-len(original_ids)
        result=dict(passed=True,books=len(audit),directory_entries_checked=checked,published_chapters=published,
            added_rows=added,original_ids_preserved=True,star_marks_preserved=True,images_and_lessons_unchanged=True,
            missing_entries=[],books_checked=counts,database_backup=original['database_backup'])
        (ROOT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='books_checked'},ensure_ascii=False))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
