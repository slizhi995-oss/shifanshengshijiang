"""Lesson ownership, chapter boundaries, and actual Markdown resource references."""
import json
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import resources
from app.core.deps import get_current_user, get_db
from app.models.base import Base
from app.models.textbook import Textbook, TextbookAsset, TextbookChapter, TextbookLesson
from app.models.user import User, UserRole
from app.services.lesson_resources import lesson_material_references

USED = 'tb-' + 'a' * 32
UNREVIEWED = 'tb-' + 'b' * 32
OTHER_CHAPTER = 'tb-' + 'c' * 32
MISSING = 'tb-' + 'd' * 32


def image(identifier, caption='斜面实验'):
    return f'![{caption}](/api/v1/textbooks/assets/{identifier}/image)'


def test_repeated_uses_keep_their_sections_and_explicit_missing_materials():
    content = f'''# 牛顿第一定律
## 教学过程
### 情境导入
观察实验照片并提出问题。
{image(USED)}
### 实验探究
{image(USED)} 比较两个斜面的运动情况。
视频待插入：伽利略斜面实验，请自行查找并补充。
图片待插入：实验装置全景。
```markdown
{image(MISSING)}
视频待插入：代码块中的示例不属于资源。
```
'''
    references, pending = lesson_material_references(content)
    assert list(references) == [USED]
    assert [use['section'] for use in references[USED]] == [
        '牛顿第一定律 / 教学过程 / 情境导入', '牛顿第一定律 / 教学过程 / 实验探究']
    assert '比较两个斜面' in references[USED][1]['excerpt']
    assert [item['kind'] for item in pending] == ['video', 'image']


@pytest_asyncio.fixture
async def environment():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add_all([User(id=i, user_code=str(i), name='测试用户', password_hash='unused', role=UserRole.STUDENT) for i in (1, 2)])
        db.add(Textbook(id=1, title='高中物理', subject='物理', grade='高中', edition='人教版', volume='必修一',
                        file_path='private.pdf', original_filename='物理.pdf', sha256='0' * 64, is_published=True))
        await db.flush()
        db.add_all([TextbookChapter(id=i, book_id=1, title='牛顿第一定律' if i == 1 else '另一章',
                                   content='教材正文', start_page=i, end_page=i, is_published=True) for i in (1, 2)])
        await db.flush()
        for identifier, chapter, reviewed in [(USED, 1, True), (UNREVIEWED, 1, False), (OTHER_CHAPTER, 2, True)]:
            db.add(TextbookAsset(asset_id=identifier, book_id=1, chapter_id=chapter, title=identifier,
                                file_path='private.png', pdf_page=chapter, width=100, height=100,
                                sha256='0' * 64, is_reviewed=reviewed, description='仅有效素材可返回的说明'))
        source = json.dumps({'book_title': '高中物理', 'chapter_title': '牛顿第一定律', 'start_page': 1,
                             'end_page': 1, 'printed_pages': '10', 'private_field': '不应公开'}, ensure_ascii=False)
        content = '\n'.join(['## 情境导入', image(USED), '## 新授', image(USED), image(UNREVIEWED),
                             image(OTHER_CHAPTER), image(MISSING), '视频待插入：斜面实验。'])
        db.add_all([TextbookLesson(id=i, user_id=i, chapter_id=1, title=f'用户{i}的教案', content=content, sources_json=source)
                    for i in (1, 2)])
        await db.commit()

    async def database():
        async with sessions() as db:
            yield db

    async def user(request: Request):
        value = request.headers.get('x-user')
        if value not in ('1', '2'):
            raise HTTPException(401, '未登录')
        return SimpleNamespace(id=int(value))

    app = FastAPI()
    app.include_router(resources.router, prefix='/resources')
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'x-user': '1'}) as client:
        yield client, sessions
    await engine.dispose()


@pytest.mark.asyncio
async def test_owner_list_filter_detail_and_unavailable_reference_boundaries(environment):
    client, _ = environment
    result = (await client.get('/resources/lessons')).json()
    assert result['total'] == 1
    assert result['items'][0]['id'] == 1
    assert result['items'][0]['image_count'] == 4  # One material may be used twice.
    assert 'private_field' not in result['items'][0]['source']
    assert 'content' not in result['items'][0]
    assert (await client.get('/resources/lessons', params={'keyword': '物理'})).json()['total'] == 1
    assert (await client.get('/resources/lessons', params={'keyword': '用户2'})).json()['total'] == 0
    assert (await client.get('/resources/lessons/2')).status_code == 404
    assert (await client.get('/resources/lessons/1', headers={'x-user': '2'})).status_code == 404
    assert (await client.get('/resources/lessons', headers={'x-user': ''})).status_code == 401
    assert (await client.get('/resources/lessons', params={'page': 0})).status_code == 422
    result = (await client.get('/resources/lessons/1')).json()
    assert result['source']['available'] is True
    assert len(result['materials'][0]['usages']) == 2
    assert [material['available'] for material in result['materials']] == [True, False, False, False]
    assert all(material['description'] == '' and material['pdf_page'] is None for material in result['materials'][1:])
    assert result['pending'][0]['kind'] == 'video'


@pytest.mark.asyncio
async def test_unpublished_source_keeps_owned_lesson_but_disables_material_access(environment):
    client, sessions = environment
    async with sessions() as db:
        (await db.get(Textbook, 1)).is_published = False
        await db.commit()
    result = (await client.get('/resources/lessons/1')).json()
    assert result['source']['available'] is False
    assert all(not material['available'] for material in result['materials'])
    assert result['content'] and result['source']['printed_pages'] == '10'
