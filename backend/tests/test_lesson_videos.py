"""Search integrity, asynchronous lifecycle, cache, failures, and private selections."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes.lesson_videos import router
from app.core.deps import get_current_user, get_db
from app.models import Base
from app.models.audio_resource import AudioLesson
from app.models.lesson_video import LessonVideoSearch
from app.models.user import User, UserRole
from app.services import lesson_videos as service

BV1, BV2 = 'BV1B7411m7LV', 'BV1xx411c7mD'


@pytest_asyncio.fixture
async def environment(monkeypatch):
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', '')
    monkeypatch.setattr(service.settings, 'VIDEO_SEARCH_ENABLED', True)
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add_all([User(id=i, user_code=f'video-{i}', name='师范生', password_hash='unused', role=UserRole.STUDENT) for i in (1, 2)])
        await db.flush()
        db.add_all([AudioLesson(id=i, user_id=i, title='自由落体运动', subject='物理', grade='高一',
            content='## 情境导入\n需要查找真空中羽毛与铁球同时下落的实验视频。') for i in (1, 2)])
        await db.commit()

    async def database():
        async with sessions() as db:
            yield db

    async def user(request: Request):
        user_id = request.headers.get('x-user')
        if user_id not in ('1', '2'):
            raise HTTPException(401)
        return SimpleNamespace(id=int(user_id))

    app = FastAPI()
    app.include_router(router, prefix='/resources')
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'x-user': '1'}) as client:
        yield client, sessions, engine
    await engine.dispose()


@pytest.mark.parametrize('url', [
    'https://www.bilibili.com.evil.test/video/' + BV1,
    'https://evil.test/video/' + BV1,
    'https://user:pass@www.bilibili.com/video/' + BV1,
    'https://www.bilibili.com:1234/video/' + BV1,
    'https://www.bilibili.com/read/cv123', 'https://b23.tv/abc',
    'javascript:alert(1)', 'https://www.bilibili.com/video/' + BV1 + '?p=0',
])
def test_pasted_links_cannot_escape_bilibili(url):
    with pytest.raises(ValueError):
        service.parse_video_url(url)


def test_normalize_real_links_and_multipart():
    assert service.parse_video_url(f'https://m.bilibili.com/video/{BV1}/?p=2&tracking=x') == (BV1, 2)
    need = dict(id='need-1', section='情境导入', purpose='实验对比')
    rows = service.normalize_candidates([
        dict(name='实验演示', url=f'https://www.bilibili.com/video/{BV1}/?p=2', summary='实验摘要'),
        dict(name='伪造链接', url=f'https://bilibili.com.evil.test/video/{BV2}'),
        dict(name='专栏', url='https://www.bilibili.com/read/cv123'),
        dict(name='App下载', url='https://www.bilibili.com/download'),
        dict(name='知乎文章', url='https://zhuanlan.zhihu.com/p/123'),
        dict(name='外站视频', url='https://media.example.org/video/fall/'),
    ], need)
    assert len(rows) == 1 and rows[0]['page'] == 2
    assert rows[0]['content_verified'] is False
    assert 'p=2' in rows[0]['embed_url'] and 'autoplay=0' in rows[0]['embed_url']


@pytest.mark.asyncio
async def test_no_key_manual_save_deduplication_and_owner_boundaries(environment):
    client, _, _ = environment
    endpoint = '/resources/audio-lessons/1/videos'
    state = (await client.get(endpoint)).json()
    assert state['status'] == 'not_configured' and not state['configured']
    assert (await client.post(endpoint + '/search', json={})).json()['status'] == 'not_configured'
    body = dict(url=f'https://www.bilibili.com/video/{BV1}?p=2', title='实验演示', section='情境导入', purpose='比较下落实验')
    first = await client.post(endpoint, json=body)
    assert first.status_code == 200
    assert len(first.json()['selected']) == 1
    video_id = first.json()['selected'][0]['id']
    assert len((await client.post(endpoint, json=body)).json()['selected']) == 1
    assert (await client.post(endpoint, json={**body, 'url': 'https://evil.test/video/' + BV1})).status_code == 422
    assert (await client.post(endpoint, json={**body, 'purpose': ' '})).status_code == 422
    assert (await client.post(endpoint, json={'candidate_id': 'invented'})).status_code == 409
    for method, path, payload in [('GET', endpoint, None), ('POST', endpoint + '/search', {}),
                                 ('POST', endpoint, body), ('DELETE', endpoint + '/' + str(video_id), None)]:
        response = await client.request(method, path, json=payload, headers={'x-user': '2'})
        assert response.status_code == 404
    assert (await client.delete(endpoint + '/' + str(video_id))).json()['selected'] == []


def mock_models(monkeypatch):
    async def model(db, user_id, prompt, data):
        if 'candidates' in data:
            return {'items': [
                dict(id=BV1 + ':1', need_id='need-1', reason='根据标题与摘要，关联真空落体实验，需预览确认'),
                dict(id='invented-video:1', need_id='need-1', reason='不能出现'),
            ]}
        return {'needs': [dict(section='情境导入', purpose='通过真空落体实验对比', keywords=['真空 羽毛 铁球 实验', '自由落体 真空 实验'])]}
    monkeypatch.setattr(service, 'model_json', model)


@pytest.mark.asyncio
async def test_background_results_cache_selection_and_search_cost_bounds(environment, monkeypatch):
    client, sessions, _ = environment
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', 'test-only-not-a-real-key')
    mock_models(monkeypatch)
    calls = []
    async def search(query):
        calls.append(query)
        return [dict(name='真空落体实验', url=f'https://www.bilibili.com/video/{BV1}', snippet='羽毛与铁球'),
                dict(name='重复', url=f'https://www.bilibili.com/video/{BV1}/?x=1'),
                dict(name='网页', url='https://www.bilibili.com/read/cv123')]
    monkeypatch.setattr(service, 'bocha_search', search)
    endpoint = '/resources/audio-lessons/1/videos'
    queued = (await client.post(endpoint + '/search', json={})).json()
    assert queued['status'] == 'queued'
    result = (await client.get(endpoint)).json()
    assert result['status'] == 'ready' and len(result['items']) == 1
    assert result['needs'][0]['method'] == 'ai' and len(calls) == 2
    assert result['items'][0]['id'] == BV1 + ':1'  # Model-invented IDs cannot become links.
    assert result['items'][0]['ranking'] == 'ai'
    assert 'essential_terms' not in result['needs'][0] and 'source_excerpt' not in result['needs'][0]
    assert 'score' not in result['items'][0] and 'evidence_quote' not in result['items'][0]
    await client.post(endpoint + '/search', json={})
    assert len(calls) == 2  # Cached reads spend no additional searches.
    assert (await client.post(endpoint + '/search', json={'force': True})).status_code == 429
    selected = (await client.post(endpoint, json={'candidate_id': BV1 + ':1', 'url': 'https://evil.test'})).json()['selected']
    assert selected[0]['bvid'] == BV1 and selected[0]['source'] == 'bocha'
    async with sessions() as db:
        lesson = await db.get(AudioLesson, 1)
        lesson.content += '\n## 实验探究\n探究新活动'
        await db.commit()
    assert (await client.get(endpoint)).json()['stale'] is True


@pytest.mark.asyncio
async def test_failure_and_restart_preserve_selected_video(environment, monkeypatch):
    client, sessions, _ = environment
    endpoint = '/resources/audio-lessons/1/videos'
    await client.post(endpoint, json=dict(url=f'https://www.bilibili.com/video/{BV1}', title='已选实验', section='探究', purpose='观察'))
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', 'test-key')
    async def failing(query):
        raise service.VideoSearchError('视频搜索超时，请稍后重试')
    monkeypatch.setattr(service, 'bocha_search', failing)
    await client.post(endpoint + '/search', json={'query': '真空落体'})
    state = (await client.get(endpoint)).json()
    assert state['status'] == 'error' and '超时' in state['message']
    assert len(state['selected']) == 1
    assert state['needs'][0]['method'] == 'manual'
    async with sessions() as db:
        job = (await db.execute(select(LessonVideoSearch))).scalar_one()
        job.status, job.started_at, job.run_id = 'searching', datetime.utcnow() - timedelta(minutes=6), 'old-job'
        await db.commit()
    state = (await client.get(endpoint)).json()
    assert state['status'] == 'error' and '中断' in state['message']
    assert len(state['selected']) == 1


@pytest.mark.asyncio
async def test_partial_failures_and_model_fallback(environment, monkeypatch):
    client, _, _ = environment
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', 'test-key')
    async def unavailable(*args, **kwargs):
        raise RuntimeError('model is unavailable')
    monkeypatch.setattr(service, 'model_json', unavailable)
    async def search(query):
        return [dict(name='真空下落实验', url=f'https://www.bilibili.com/video/{BV2}', snippet='观察羽毛和铁球')]
    monkeypatch.setattr(service, 'bocha_search', search)
    endpoint = '/resources/audio-lessons/1/videos'
    await client.post(endpoint + '/search', json={})
    result = (await client.get(endpoint)).json()
    assert result['status'] == 'ready' and result['items'][0]['ranking'] == 'search'
    assert result['needs'][0]['method'] == 'text'
    assert result['items'][0]['content_verified'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('rows,expected', [([], 'no_results')])
async def test_empty_search_is_explicit(environment, monkeypatch, rows, expected):
    client, _, _ = environment
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', 'test-key')
    async def search(query):
        return rows
    monkeypatch.setattr(service, 'bocha_search', search)
    endpoint = '/resources/audio-lessons/1/videos'
    await client.post(endpoint + '/search', json={'query': '空结果测试'})
    assert (await client.get(endpoint)).json()['status'] == expected


@pytest.mark.asyncio
async def test_generation_hook_commits_then_schedules_and_duplicate_claim(environment, monkeypatch):
    _, sessions, engine = environment
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', 'test-key')
    async with sessions() as db:
        lesson = await db.get(AudioLesson, 1)
        tasks = BackgroundTasks()
        await service.prepare_generated_search(db, lesson, tasks)
        assert len(tasks.tasks) == 1
        assert tasks.tasks[0].func is service.run_search
        assert tasks.tasks[0].args[:3] == (engine, 1, 1)
        assert await service.queue_search(db, lesson) is None
    async with sessions() as db:
        state = (await db.execute(select(LessonVideoSearch))).scalar_one()
        assert state.status == 'queued'


@pytest.mark.asyncio
@pytest.mark.parametrize('status,payload,expected', [
    (200, {'code': 200, 'data': {'webPages': {'value': []}}}, None),
    (200, {'code': 500, 'message': 'secret echoed test-key'}, '异常'),
    (200, {'data': {}}, '有效'), (401, {}, '密钥'), (403, {}, '余额'), (429, {}, '繁忙'), (500, {}, '不可用'),
])
async def test_bocha_contract_and_safe_errors(monkeypatch, status, payload, expected):
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', 'test-key')
    original = httpx.AsyncClient
    def handler(request):
        assert request.url.path == '/v1/web-search'
        body = json.loads(request.content)
        assert body['query'] == '真空落体' and body['include'] == 'bilibili.com'
        assert body['count'] == 10 and body['summary'] is True
        assert request.headers['Authorization'] == 'Bearer test-key'
        return httpx.Response(status, json=payload)
    monkeypatch.setattr(service.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    if expected:
        with pytest.raises(service.VideoSearchError, match=expected) as error:
            await service.bocha_search('真空落体')
        assert 'test-key' not in str(error.value)
    else:
        assert await service.bocha_search('真空落体') == []


@pytest.mark.asyncio
async def test_experimental_empty_cache_is_invalidated_and_original_search_runs(environment,monkeypatch):
    client,sessions,_=environment
    monkeypatch.setattr(service.settings,'BOCHA_API_KEY','test-key')
    mock_models(monkeypatch)
    async def search(query):
        return [dict(name='真空落体实验',url=f'https://www.bilibili.com/video/{BV1}')]
    monkeypatch.setattr(service,'bocha_search',search)
    async with sessions() as db:
        db.add(LessonVideoSearch(lesson_id=1,status='no_results',fingerprint='v11-old-policy',
            started_at=datetime.utcnow()-timedelta(minutes=3),completed_at=datetime.utcnow(),
            message='严格活动匹配未通过',needs_json='[]',items_json='[]'))
        await db.commit()
    endpoint='/resources/audio-lessons/1/videos'
    cached=(await client.get(endpoint)).json()
    assert cached['status']=='idle' and cached['stale'] is True
    assert cached['message']==''
    await client.post(endpoint+'/search',json={})
    result=(await client.get(endpoint)).json()
    assert result['status']=='ready' and len(result['items'])==1
    assert result['search_scope']=='bilibili'
    assert result['items'][0]['url']==f'https://www.bilibili.com/video/{BV1}/'


@pytest.mark.asyncio
async def test_cover_metadata_and_owner_checks_remain_available(environment,monkeypatch):
    from app.api.routes import lesson_videos as video_routes
    client,_,_=environment
    async def metadata(bvid):
        return dict(availability='available',title='真空落体实验',cover_url='https://i0.hdslb.com/bfs/archive/cover.jpg')
    monkeypatch.setattr(video_routes,'video_metadata',metadata)
    endpoint='/resources/audio-lessons/1/videos'
    await client.post(endpoint,json=dict(url=f'https://www.bilibili.com/video/{BV1}',title='实验',section='导入',purpose='观察'))
    assert (await client.get(endpoint+f'/{BV1}/metadata')).json()['cover_url'].endswith('cover.jpg')
    assert (await client.get(endpoint+f'/{BV1}/metadata',headers={'x-user':'2'})).status_code==404
    assert (await client.get(endpoint+f'/{BV2}/metadata')).status_code==404


async def bind_textbook(sessions):
    from app.models.textbook import Textbook, TextbookChapter, TextbookAsset, TextbookLesson
    async with sessions() as db:
        db.add(Textbook(id=10, title='物理必修第一册', subject='物理', grade='高一', file_path='unused.pdf',
            original_filename='unused.pdf', sha256='a' * 64, is_published=True))
        await db.flush()
        db.add_all([TextbookChapter(id=10, book_id=10, title='自由落体运动', start_page=10, end_page=12,
            content='牛顿管实验：抽出管内空气，观察羽毛与铁球同时下落。', is_published=True),
            TextbookChapter(id=11, book_id=10, title='其他小节', start_page=13, end_page=14,
            content='不应读到的相邻章节', is_published=True)])
        await db.flush()
        for identifier, chapter_id, reviewed in ((10, 10, True), (11, 11, True), (12, 10, False)):
            db.add(TextbookAsset(id=identifier, asset_id=f'test-{identifier}', book_id=10, chapter_id=chapter_id,
                title=f'图{identifier}', file_path='unused.png', pdf_page=10, width=100, height=100,
                sha256=str(identifier) * 32, description=f'图注{identifier}', is_reviewed=reviewed))
        db.add(TextbookLesson(id=10, user_id=1, chapter_id=10, title='自由落体运动', content='教案', sources_json='{}'))
        lesson = await db.get(AudioLesson, 1)
        lesson.textbook_lesson_id = 10
        lesson.source_json = json.dumps({'chapter_id': 10, 'book_id': 10})
        await db.commit()


@pytest.mark.asyncio
async def test_textbook_enriches_extraction_without_changing_ranking_or_manual_queries(environment, monkeypatch):
    client, sessions, _ = environment
    await bind_textbook(sessions)
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', 'test-key')
    calls = []
    async def model(db, user_id, prompt, data):
        calls.append(data)
        if 'candidates' in data:
            assert 'textbook' not in data  # Original loose ranking remains unchanged.
            return {'items': [dict(id=BV1 + ':1', need_id='need-1', reason='标题相关，需预览确认')]}
        assert data['textbook']['text'].startswith('牛顿管实验')
        assert [figure['description'] for figure in data['textbook']['figures']] == ['图注10']
        assert '不应读到' not in json.dumps(data, ensure_ascii=False)
        assert '教案决定视频的用途' in prompt
        return {'needs': [dict(section='情境导入', purpose='对比真空落体', keywords=['牛顿管 实验', '真空 羽毛 铁球'])]}
    async def search(query):
        return [dict(name='牛顿管实验', url=f'https://www.bilibili.com/video/{BV1}')]
    monkeypatch.setattr(service, 'model_json', model)
    monkeypatch.setattr(service, 'bocha_search', search)
    endpoint = '/resources/audio-lessons/1/videos'
    await client.post(endpoint + '/search', json={})
    result = (await client.get(endpoint)).json()
    assert result['status'] == 'ready' and result['search_scope'] == 'bilibili'
    assert result['needs'][0]['textbook']['chapter_title'] == '自由落体运动'
    assert len(calls) == 2
    async with sessions() as db:
        lesson = await db.get(AudioLesson, 1)
        assert await service.extract_needs(db, lesson, '指定关键词') == [dict(id='need-1', section='自定义检索',
            purpose='指定关键词', keywords=['指定关键词'], method='manual')]
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid', ['unpublished', 'subject', 'owner', 'binding', 'book', 'malformed'])
async def test_invalid_textbook_binding_falls_back_to_original_extraction(environment, monkeypatch, invalid):
    from app.models.textbook import Textbook, TextbookChapter, TextbookLesson
    _, sessions, _ = environment
    await bind_textbook(sessions)
    async with sessions() as db:
        lesson = await db.get(AudioLesson, 1)
        if invalid == 'unpublished':
            (await db.get(TextbookChapter, 10)).is_published = False
        elif invalid == 'subject':
            (await db.get(Textbook, 10)).subject = '化学'
        elif invalid == 'owner':
            (await db.get(TextbookLesson, 10)).user_id = 2
        elif invalid == 'binding':
            lesson.source_json = '{"chapter_id":11,"book_id":10}'
        elif invalid == 'book':
            lesson.source_json = '{"chapter_id":10,"book_id":99}'
        else:
            lesson.textbook_lesson_id, lesson.source_json = None, '[invalid'
        await db.commit()
        context = await service.textbook_context(db, lesson)
        assert context is None
        async def model(db, user_id, prompt, data):
            assert 'textbook' not in data
            return {'needs': [dict(section='导入', purpose='观察下落', keywords=['真空落体'])]}
        monkeypatch.setattr(service, 'model_json', model)
        assert (await service.extract_needs(db, lesson, textbook=context))[0]['keywords'] == ['真空落体']


@pytest.mark.asyncio
async def test_textbook_changes_expire_automatic_cache_but_not_manual_search(environment, monkeypatch):
    from app.models.textbook import TextbookChapter
    client, sessions, _ = environment
    await bind_textbook(sessions)
    monkeypatch.setattr(service.settings, 'BOCHA_API_KEY', 'test-key')
    mock_models(monkeypatch)
    async def search(query):
        return [dict(name='真空落体实验', url=f'https://www.bilibili.com/video/{BV1}')]
    monkeypatch.setattr(service, 'bocha_search', search)
    endpoint = '/resources/audio-lessons/1/videos'
    await client.post(endpoint + '/search', json={})
    assert (await client.get(endpoint)).json()['stale'] is False
    async with sessions() as db:
        lesson = await db.get(AudioLesson, 1)
        manual_before = await service.current_fingerprint(db, lesson, '自定义词')
        (await db.get(TextbookChapter, 10)).content += '更新实验图注。'
        await db.commit()
        assert await service.current_fingerprint(db, lesson, '自定义词') == manual_before
    result = (await client.get(endpoint)).json()
    assert result['status'] == 'idle' and result['stale'] is True and result['items'] == []
    assert (await client.post(endpoint, json={'candidate_id': BV1 + ':1'})).status_code == 409
