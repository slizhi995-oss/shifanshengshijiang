"""Real private ingestion, confirmed retrieval and lesson attachment.

Only the language-model response is stubbed; SQL, HTTP permissions, image
files, Markdown references and ZIP bundles remain real.
"""
import io
import json
import zipfile
from types import SimpleNamespace

import fitz
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request, HTTPException
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.api.routes import textbooks, ai
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.ai_config import AIModelConfig
from app.models.textbook import TextbookAsset, TextbookLesson, TextbookPage
from app.services import textbook_service as materials
from app.services.ai_model_service import DynamicAIService
from app.services.lesson_materials import asset_url, markdown_asset_ids


def image_bytes(color='navy'):
    result = io.BytesIO()
    Image.new('RGB', (240, 140), color).save(result, 'PNG')
    return result.getvalue()


def pdf_bytes():
    with fitz.open() as document:
        for n in range(2):
            page = document.new_page()
            page.insert_text((70, 100), 'First law. Galileo inclined plane experiment. ' * 3)
            page.insert_image(fitz.Rect(70, 200, 310, 340), stream=image_bytes('navy' if n == 0 else 'green'))
        return document.tobytes()


@pytest_asyncio.fixture
async def environment(tmp_path, monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    for name, value in [('AI_ENABLED', True), ('TEXTBOOK_STORAGE_DIR', str(tmp_path / 'books'))]:
        monkeypatch.setattr(materials.settings, name, value)
    async with sessions() as db:
        db.add_all([User(user_code=str(i), name='测试用户', password_hash='unused',
                        role=UserRole.ADMIN if i == 3 else UserRole.STUDENT) for i in (1, 2, 3)])
        db.add(AIModelConfig(name='文本模型', model_id='stub', provider='openai', model_type='text',
                            api_key='isolated-test-secret', is_enabled=True, is_default=True))
        await db.commit()
    async def database():
        async with sessions() as db:
            yield db
    async def user(request: Request):
        identifier = request.headers.get('x-user')
        if identifier not in ('1', '2', '3'):
            raise HTTPException(401, '未登录')
        return SimpleNamespace(id=int(identifier), role=UserRole.ADMIN if identifier == '3' else UserRole.STUDENT)
    app = FastAPI()
    for router, prefix in [(textbooks.router, '/textbooks'), (ai.router, '/ai')]:
        app.include_router(router, prefix=prefix)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'x-user': '1'}) as client:
        yield client, sessions, tmp_path
    await engine.dispose()


ADMIN = {'x-user': '3'}
CHAPTER_TEXT = '牛顿第一定律：一切物体总保持匀速直线运动状态或静止状态，直到有外力迫使它改变这种状态为止。观察伽利略斜面实验的真实频闪照片，注意真实实验仍存在摩擦。'


async def import_reviewed(client):
    response = await client.post('/textbooks', headers=ADMIN, files={'file': ('test.pdf', pdf_bytes(), 'application/pdf')},
        data={'title': '物理 必修第一册', 'subject': '物理', 'grade': '高中一年级', 'edition': '测试人教版', 'volume': '必修第一册'})
    assert response.status_code == 201, response.text
    book = response.json()['data']
    assert book['page_count'] == 2
    chapter = (await client.post(f'/textbooks/{book["id"]}/chapters', headers=ADMIN,
        json={'title': '牛顿第一定律', 'start_page': 1, 'end_page': 1, 'content': CHAPTER_TEXT, 'is_published': True})).json()['data']
    images = (await client.get(f'/textbooks/{book["id"]}/assets', headers=ADMIN)).json()['data']
    assert len(images) == 2
    image = images[0]
    response = await client.patch(f'/textbooks/assets/{image["asset_id"]}', headers=ADMIN, json={
        'title': '伽利略斜面实验频闪照片', 'chapter_id': chapter['id'], 'figure_number': '图4.1-1',
        'description': '真实斜面实验照片，观察小球运动。', 'tags': ['伽利略', '斜面实验', '频闪照片'],
        'conditions': '真实实验存在摩擦，不能当作无摩擦理想实验照片。', 'is_reviewed': True})
    assert response.status_code == 200, response.text
    return book, chapter, response.json()['data'], images[1]


def generation_payload(chapter_id):
    return {'subject': '物理', 'grade': '高中一年级', 'topic': '牛顿第一定律', 'duration': 15,
            'use_textbook': True, 'textbook_chapter_id': chapter_id}




@pytest.mark.asyncio
async def test_admin_upload_draft_review_and_private_permissions(environment):
    client, sessions, root = environment
    assert (await client.post('/textbooks', files={'file': ('t.pdf', pdf_bytes())},
        data={'title': 't', 'subject': '物理', 'grade': '高中一年级'})).status_code == 403
    book, chapter, image, other = await import_reviewed(client)
    assert len((await client.get('/textbooks')).json()['data']) == 1
    recommended = (await client.get('/textbooks/recommend', params={'subject': '物理', 'grade': '高中一年级', 'topic': '牛顿第一定律'})).json()['data']
    assert recommended[0]['id'] == chapter['id'] and recommended[0]['score'] > 0
    assert (await client.get(f'/textbooks/assets/{other["asset_id"]}/image')).status_code == 404
    assert (await client.get(f'/textbooks/assets/{image["asset_id"]}/image', headers={'x-user': ''})).status_code == 401
    response = await client.get(f'/textbooks/assets/{image["asset_id"]}/image')
    assert response.status_code == 200 and 'no-store' in response.headers['cache-control']
    assert (await client.get(f'/textbooks/{book["id"]}/assets')).status_code == 403
    assert (await client.get(f'/textbooks/{book["id"]}/pdf')).content.startswith(b'%PDF-')
    book_edit = {key: book[key] for key in ('title', 'subject', 'grade', 'publisher', 'edition', 'volume')}
    book_edit['edition'] = '核对后的版次'
    assert (await client.patch(f'/textbooks/{book["id"]}', json=book_edit)).status_code == 403
    assert (await client.patch(f'/textbooks/{book["id"]}', headers=ADMIN, json=book_edit)).json()['data']['edition'] == '核对后的版次'
    assert str(root) not in json.dumps((await client.get(f'/textbooks/chapters/{chapter["id"]}')).json())
    async with sessions() as db:
        assert len((await db.execute(select(TextbookPage))).scalars().all()) == 2
    invalid = {**image, 'chapter_id': chapter['id'], 'is_reviewed': True}
    invalid.pop('tags'); invalid['tags'] = []
    assert (await client.patch(f'/textbooks/assets/{image["asset_id"]}', headers=ADMIN, json=invalid)).status_code == 422


@pytest.mark.asyncio
async def test_confirmed_chapter_prompt_image_matching_and_bundle(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    calls = []
    api = DynamicAIService()
    async def chat(**kwargs):
        calls.append(kwargs)
        assert kwargs['usage_type'] == 'generation'
        if len(calls) == 1:
            assert CHAPTER_TEXT in kwargs['messages'][0]['content']
            assert kwargs['messages'][0]['role'] == 'system'
            assert '牛顿第一定律' in kwargs['messages'][1]['content']
            return '# 教学过程\n\n观察真实的伽利略斜面实验频闪照片，比较小球运动。\n\n[[图片：伽利略斜面实验频闪照片，用于观察真实实验]]\n\n[[图片：没有的宇宙飞船照片]]\n\n视频待插入，请自行查找并补充。'
        candidates = json.loads(kwargs['messages'][1]['content'])
        assert len(candidates) == 1
        assert {x['id'] for x in candidates[0]['candidates']} == {image['asset_id']}
        assert '摩擦' in candidates[0]['candidates'][0]['conditions_and_limits']
        return json.dumps({'selections': [{'index': 0, 'asset_id': image['asset_id']}]})
    monkeypatch.setattr(api, 'chat_completion', chat)
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', lambda: api)
    response = await client.post('/ai/generate', json=generation_payload(chapter['id']))
    assert response.status_code == 200, response.text
    lesson = response.json()['data']
    assert markdown_asset_ids(lesson['content']) == [image['asset_id']]
    assert '图片待插入：没有的宇宙飞船照片' in lesson['content']
    assert '视频待插入' in lesson['content'] and '教材依据' not in lesson['content']
    assert lesson['sources']['start_page']==lesson['sources']['end_page']==1
    assert len(calls) == 2 and lesson['sources']['chapter_id'] == chapter['id']
    downloaded = await client.get(f'/textbooks/lessons/{lesson["lesson_id"]}/bundle')
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert f'images/{image["asset_id"]}.png' in archive.namelist()
        text = archive.read('教案.md').decode()
        assert f'(images/{image["asset_id"]}.png)' in text and '/api/v1/' not in text
        assert archive.read(f'images/{image["asset_id"]}.png') == (await client.get(f'/textbooks/assets/{image["asset_id"]}/image')).content
    assert (await client.get(f'/textbooks/lessons/{lesson["lesson_id"]}/bundle', headers={'x-user': '2'})).status_code == 404
    async with sessions() as db:
        assert len((await db.execute(select(TextbookLesson))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_missing_wrong_grade_and_unpublished_chapter_never_call_model(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    class Forbidden:
        async def generate_lesson_plan(self, **kwargs):
            pytest.fail('Invalid confirmation must be rejected before contacting the LLM')
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', Forbidden)
    for changes in [{'textbook_chapter_id': None}, {'grade': '高中二年级'}, {'subject': '数学'}, {'stream': True}]:
        assert (await client.post('/ai/generate', json={**generation_payload(chapter['id']), **changes})).status_code == 422
    body = {'title': chapter['title'], 'start_page': 1, 'end_page': 1, 'content': CHAPTER_TEXT, 'is_published': False}
    assert (await client.put(f'/textbooks/chapters/{chapter["id"]}', headers=ADMIN, json=body)).status_code == 200
    assert (await client.post('/ai/generate', json=generation_payload(chapter['id']))).status_code == 422
    assert (await client.get(f'/textbooks/assets/{image["asset_id"]}/image')).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('model_image', ['external', 'other-chapter', 'invented'])
async def test_model_cannot_insert_unretrieved_images(environment, monkeypatch, model_image):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    destination = 'https://example.test/fake.png' if model_image == 'external' else asset_url(other['asset_id'] if model_image == 'other-chapter' else 'tb-' + '0' * 32)
    class Invalid:
        async def generate_lesson_plan(self, **kwargs):
            return '# 教学过程\n\n![伽利略](' + destination + ')'
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', Invalid)
    response = await client.post('/ai/generate', json=generation_payload(chapter['id']))
    assert response.status_code == 200
    data = response.json()['data']
    assert data['asset_ids'] == []
    assert '图片待插入：伽利略' in data['content']
    assert any('非教材图片引用' in warning for warning in data['material_warnings'])
    async with sessions() as db:
        assert len((await db.execute(select(TextbookLesson))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_excess_image_requests_keep_lesson_and_cap_selector_work(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    calls = []
    class ManyImages:
        async def generate_lesson_plan(self, **kwargs):
            return '# 教学过程\n\n' + '\n\n'.join(
                f'活动{i} [[图片：伽利略斜面实验照片]]' for i in range(17))
        async def chat_completion(self, **kwargs):
            tasks = json.loads(kwargs['messages'][1]['content'])
            calls.append(tasks)
            return json.dumps({'selections': [
                {'index': task['index'], 'asset_id': image['asset_id']} for task in tasks]})
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', ManyImages)
    response = await client.post('/ai/generate', json=generation_payload(chapter['id']))
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert len(calls) == 1 and len(calls[0]) == 16
    assert data['content'].count(asset_url(image['asset_id'])) == 16
    assert '图片待插入：伽利略斜面实验照片' in data['content']
    assert any('前16处' in warning for warning in data['material_warnings'])


@pytest.mark.asyncio
async def test_manual_crop_upload_is_private_until_review_and_scope_checked(environment):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    endpoint = f'/textbooks/{book["id"]}/assets'
    assert (await client.post(endpoint, files={'file': ('crop.png', image_bytes())}, data={'pdf_page': 1})).status_code == 403
    assert (await client.post(endpoint, headers=ADMIN, files={'file': ('bad.png', b'bad')}, data={'pdf_page': 1})).status_code == 422
    assert (await client.post(endpoint, headers=ADMIN, files={'file': ('crop.png', image_bytes())}, data={'pdf_page': 99})).status_code == 422
    crop = (await client.post(endpoint, headers=ADMIN, files={'file': ('crop.png', image_bytes())}, data={'pdf_page': 2})).json()['data']
    assert not crop['is_reviewed'] and crop['chapter_id'] is None
    assert (await client.get(f'/textbooks/assets/{crop["asset_id"]}/image')).status_code == 404
    update = {'title': '错误页码图', 'chapter_id': chapter['id'], 'tags': ['斜面'], 'description': '斜面', 'is_reviewed': True}
    assert (await client.patch(f'/textbooks/assets/{crop["asset_id"]}', headers=ADMIN, json=update)).status_code == 422
    assert (await client.post(f'/textbooks/{book["id"]}/chapters', headers=ADMIN,
        json={'title': '空白扫描', 'start_page': 2, 'end_page': 2, 'content': '[PDF第2页]', 'is_published': True})).status_code == 422


@pytest.mark.asyncio
async def test_exact_figure_still_checks_conditions_and_allows_null(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    class CheckConditions:
        async def generate_lesson_plan(self, **kwargs):
            return '# 教学过程\n\n需要可展示无摩擦无限运动过程的材料。\n\n[[图片：图4.1-1，无摩擦无限运动过程]]'
        async def chat_completion(self, **kwargs):
            tasks = json.loads(kwargs['messages'][1]['content'])
            assert len(tasks) == 1 and tasks[0]['candidates'][0]['id'] == image['asset_id']
            assert '真实实验存在摩擦' in tasks[0]['candidates'][0]['conditions_and_limits']
            return '{"selections":[{"index":0,"asset_id":null}]}'
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', CheckConditions)
    result = (await client.post('/ai/generate', json=generation_payload(chapter['id']))).json()['data']
    assert result['asset_ids'] == [] and '图片待插入：图4.1-1' in result['content']


@pytest.mark.asyncio
async def test_unknown_candidate_selection_rejected_and_corrupt_bundle_detected(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    class BadSelection:
        async def generate_lesson_plan(self, **kwargs):
            return '# 教学过程\n\n[[图片：伽利略斜面实验]]'
        async def chat_completion(self, **kwargs):
            return json.dumps({'selections': [{'index': 0, 'asset_id': other['asset_id']}]})
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', BadSelection)
    invalid = await client.post('/ai/generate', json=generation_payload(chapter['id']))
    assert invalid.status_code == 200
    assert invalid.json()['data']['asset_ids'] == []
    assert invalid.json()['data']['material_warnings'] and '图片待插入' in invalid.json()['data']['content']
    async with sessions() as db:
        context = await materials.lesson_context(db, chapter['id'], '物理', '高中一年级')
        result = await materials.attach_lesson_images(db, None, 1, None,
            '# 教学过程\n\n![伽利略](' + asset_url(image['asset_id']) + ')', context)
        row = (await db.execute(select(TextbookAsset).where(TextbookAsset.asset_id == image['asset_id']))).scalar_one()
        materials.private_path(row.file_path).write_bytes(b'corrupted')
    assert (await client.get(f'/textbooks/lessons/{result["lesson_id"]}/bundle')).status_code == 409


@pytest.mark.asyncio
async def test_selector_repairs_missing_duplicate_decisions_once(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    calls = []
    class Incomplete:
        async def generate_lesson_plan(self, **kwargs):
            return '# 教学过程\n\n[[图片：图4.1-1，观察真实斜面实验]]\n\n再次观察照片，注意摩擦。\n\n[[图片：图4.1-1，观察真实斜面实验]]'
        async def chat_completion(self, **kwargs):
            calls.append(kwargs)
            selected = [{'index': 0, 'asset_id': image['asset_id']}]
            if len(calls) == 2:
                assert '上一次回复未通过' in kwargs['messages'][0]['content']
                selected.append({'index': 1, 'asset_id': image['asset_id']})
            return json.dumps({'selections': selected})
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', Incomplete)
    result = (await client.post('/ai/generate', json=generation_payload(chapter['id']))).json()['data']
    assert len(calls) == 2 and result['asset_ids'] == [image['asset_id']]
    assert result['content'].count(asset_url(image['asset_id'])) == 2
    assert not result['material_warnings']


