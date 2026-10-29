"""Publication boundaries and administrator-managed shared fallback videos."""
from types import SimpleNamespace
from io import BytesIO

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import teaching_tips
from app.core.deps import get_current_user, get_db
from app.models import Base
from app.models.user import UserRole
from app.services import teaching_tip_covers

BV = 'BV1B7411m7LV'
BODY = dict(url=f'https://m.bilibili.com/video/{BV}/?p=2&tracking=discard',
            title='试讲导入技巧', category='导入设计', description='情境导入的方法',
            is_published=False, sort_order=5)


@pytest_asyncio.fixture
async def client(monkeypatch, tmp_path):
    upload_directory = tmp_path / 'uploads'
    upload_directory.mkdir()
    monkeypatch.setattr(teaching_tip_covers.settings, 'UPLOAD_DIR', str(upload_directory))
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def database():
        async with sessions() as db:
            yield db

    async def user(request: Request):
        role = request.headers.get('x-role')
        if role not in ('admin', 'student', 'instructor'):
            raise HTTPException(401)
        return SimpleNamespace(id=1, role=UserRole(role))

    async def metadata(bvid):
        assert bvid == BV
        return dict(title='B站标题', cover_url='https://i0.hdslb.com/bfs/archive/tip.jpg', availability='available')

    monkeypatch.setattr(teaching_tips, 'video_page_metadata', metadata)
    app = FastAPI()
    app.include_router(teaching_tips.router)
    app.mount('/uploads', StaticFiles(directory=upload_directory), name='uploads')
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'x-role': 'admin'}) as value:
        yield value
    await engine.dispose()


@pytest.mark.asyncio
async def test_publication_order_edit_delete_and_canonical_link(client):
    endpoint = '/admin/teaching-tips'
    created = await client.post(endpoint, json=BODY)
    assert created.status_code == 201
    item = created.json()
    assert item['url'] == f'https://www.bilibili.com/video/{BV}/?p=2'
    assert (await client.get('/resources/teaching-tips', headers={'x-role': 'student'})).json() == {'items': []}
    assert len((await client.get(endpoint)).json()['items']) == 1
    assert (await client.post(endpoint, json=BODY)).status_code == 409
    assert (await client.put(f"{endpoint}/{item['id']}", json={**BODY, 'is_published': True})).status_code == 200
    other = await client.post(endpoint, json={**BODY, 'url': BODY['url'].replace('p=2', 'p=3'), 'title': '板书技巧', 'is_published': True, 'sort_order': 1})
    assert other.status_code == 201
    visible = (await client.get('/resources/teaching-tips', headers={'x-role': 'student'})).json()['items']
    assert [row['title'] for row in visible] == ['板书技巧', '试讲导入技巧']
    assert (await client.put(f"{endpoint}/{item['id']}", json={**BODY, 'title': '新标题'})).status_code == 200
    assert len((await client.get('/resources/teaching-tips')).json()['items']) == 1
    assert (await client.delete(f"{endpoint}/{other.json()['id']}")).status_code == 204
    assert (await client.get('/resources/teaching-tips')).json()['items'] == []
    assert (await client.delete(f"{endpoint}/999")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['student', 'instructor'])
async def test_nonadmins_cannot_read_drafts_or_mutate(client, role):
    headers = {'x-role': role}
    assert (await client.get('/admin/teaching-tips', headers=headers)).status_code == 403
    assert (await client.post('/admin/teaching-tips', json=BODY, headers=headers)).status_code == 403
    assert (await client.put('/admin/teaching-tips/1', json=BODY, headers=headers)).status_code == 403
    assert (await client.delete('/admin/teaching-tips/1', headers=headers)).status_code == 403
    assert (await client.post('/admin/teaching-tips/metadata', json={'url': BODY['url']}, headers=headers)).status_code == 403
    assert (await client.get('/resources/teaching-tips', headers={'x-role': ''})).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize('changes', [
    {'url': 'https://www.bilibili.com.evil.test/video/' + BV},
    {'url': 'javascript:alert(1)'}, {'title': '   '}, {'category': ' '},
    {'cover_url': 'https://evil.test/a.jpg'}, {'sort_order': -1},
])
async def test_invalid_inputs(client, changes):
    assert (await client.post('/admin/teaching-tips', json={**BODY, **changes})).status_code == 422


@pytest.mark.asyncio
async def test_metadata_can_be_read_without_a_lesson(client):
    result = await client.post('/admin/teaching-tips/metadata', json={'url': BODY['url']})
    assert result.status_code == 200
    assert result.json()['title'] == 'B站标题'
    assert (await client.post('/admin/teaching-tips/metadata', json={'url': 'https://evil.test/'})).status_code == 422


@pytest.mark.asyncio
async def test_missing_cover_is_filled_without_replacing_an_explicit_cover(client):
    created = (await client.post('/admin/teaching-tips', json=BODY)).json()
    assert created['cover_url'] == 'https://i0.hdslb.com/bfs/archive/tip.jpg'
    custom = 'https://i0.hdslb.com/bfs/archive/custom.jpg'
    updated = await client.put(f"/admin/teaching-tips/{created['id']}", json={**BODY, 'cover_url': custom})
    assert updated.json()['cover_url'] == custom


@pytest.mark.asyncio
async def test_students_can_resolve_published_covers_but_not_drafts(client):
    created = (await client.post('/admin/teaching-tips', json=BODY)).json()
    endpoint = f"/resources/teaching-tips/{created['id']}/metadata"
    assert (await client.get(endpoint, headers={'x-role': 'student'})).status_code == 404
    await client.put(f"/admin/teaching-tips/{created['id']}", json={**BODY, 'is_published': True})
    result = await client.get(endpoint, headers={'x-role': 'student'})
    assert result.status_code == 200
    assert result.json()['cover_url'] == 'https://i0.hdslb.com/bfs/archive/tip.jpg'
    assert (await client.get(endpoint, headers={'x-role': ''})).status_code == 401


@pytest.mark.asyncio
async def test_unavailable_metadata_preserves_saved_cover(client, monkeypatch):
    async def unavailable(bvid):
        return dict(title='', cover_url='', availability='unknown')

    monkeypatch.setattr(teaching_tips, 'video_page_metadata', unavailable)
    custom = 'https://i0.hdslb.com/bfs/archive/custom.jpg'
    created = await client.post('/admin/teaching-tips', json={**BODY, 'is_published': True, 'cover_url': custom})
    result = await client.get(f"/resources/teaching-tips/{created.json()['id']}/metadata", headers={'x-role': 'student'})
    assert result.json() == {'cover_url': custom}
    other = await client.post('/admin/teaching-tips', json={**BODY, 'url': BODY['url'].replace('p=2', 'p=3')})
    assert other.status_code == 201
    assert other.json()['cover_url'] == ''


@pytest.mark.asyncio
async def test_jsonld_cover_flows_through_admin_save_and_published_endpoint(client, monkeypatch):
    from app.services import bilibili_metadata

    bilibili_metadata._page_cache.clear()
    bilibili_metadata._page_pending.clear()
    original = httpx.AsyncClient
    calls = []

    async def handler(request):
        calls.append(request)
        assert str(request.url) == f'https://www.bilibili.com/video/{BV}/'
        return httpx.Response(200, text='<script type="application/ld+json">'
                              '{"@type":"VideoObject","thumbnailUrl":["//i0.hdslb.com/bfs/archive/actual.jpg"]}'
                              '</script>')

    monkeypatch.setattr(bilibili_metadata.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr(teaching_tips, 'video_page_metadata', bilibili_metadata.video_page_metadata)
    created = await client.post('/admin/teaching-tips', json={**BODY, 'is_published': True})
    assert created.status_code == 201
    assert created.json()['cover_url'] == 'https://i0.hdslb.com/bfs/archive/actual.jpg'
    endpoint = f"/resources/teaching-tips/{created.json()['id']}/metadata"
    published = await client.get(endpoint, headers={'x-role': 'student'})
    assert published.json() == {'cover_url': 'https://i0.hdslb.com/bfs/archive/actual.jpg'}
    assert len(calls) == 1
    bilibili_metadata._page_cache.clear()


def cover_bytes(format='PNG', size=(640, 360)):
    image = Image.new('RGB', size, '#155e75')
    buffer = BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize('format,media_type', [('PNG', 'image/png'), ('JPEG', 'image/jpeg'), ('WEBP', 'image/webp')])
async def test_uploaded_cover_is_saved_served_and_preferred_without_bilibili(client, monkeypatch, format, media_type):
    async def forbidden_metadata(bvid):
        raise AssertionError('An uploaded cover must not depend on Bilibili')

    monkeypatch.setattr(teaching_tips, 'video_page_metadata', forbidden_metadata)
    payload = cover_bytes(format, (1920, 1080))
    uploaded = await client.post('/admin/teaching-tips/covers', files={'file': ('../../cover.png', payload, media_type)})
    assert uploaded.status_code == 201
    url = uploaded.json()['cover_url']
    assert url.startswith('/uploads/teaching-tip-covers/') and url.endswith('.jpg')
    created = await client.post('/admin/teaching-tips', json={**BODY, 'cover_url': url, 'is_published': True})
    assert created.status_code == 201
    assert created.json()['cover_url'] == url
    published = (await client.get('/resources/teaching-tips', headers={'x-role': 'student'})).json()['items']
    assert published[0]['cover_url'] == url
    endpoint = f"/resources/teaching-tips/{created.json()['id']}/metadata"
    assert (await client.get(endpoint, headers={'x-role': 'student'})).json() == {'cover_url': url}
    image = await client.get(url)
    assert image.status_code == 200
    assert image.headers['content-type'] == 'image/jpeg'
    with Image.open(BytesIO(image.content)) as decoded:
        assert decoded.size == (1280, 720)
        assert decoded.format == 'JPEG'
    duplicate = await client.post('/admin/teaching-tips/covers', files={'file': ('duplicate.png', payload, media_type)})
    assert duplicate.json()['cover_url'] == url
    assert len(list(teaching_tip_covers.cover_directory().iterdir())) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('role,expected_status', [('student', 403), ('instructor', 403), ('', 401)])
async def test_cover_upload_requires_administrator(client, role, expected_status):
    result = await client.post('/admin/teaching-tips/covers', files={'file': ('cover.png', cover_bytes(), 'image/png')},
                               headers={'x-role': role})
    assert result.status_code == expected_status
    assert not teaching_tip_covers.cover_directory().exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [b'', b'not an image', b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
                                   b'x' * (teaching_tip_covers.MAX_COVER_BYTES + 1)],
                         ids=['empty', 'invalid-image', 'svg', 'oversized'])
async def test_invalid_cover_uploads_do_not_create_files(client, payload):
    result = await client.post('/admin/teaching-tips/covers', files={'file': ('cover.png', payload, 'image/png')})
    assert result.status_code == 422
    assert not teaching_tip_covers.cover_directory().exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('url', ['/uploads/teaching-tip-covers/../../config.jpg',
                               '/uploads/teaching-tip-covers/' + 'a' * 64 + '.jpg',
                               '/uploads/other.jpg'])
async def test_local_cover_must_reference_a_real_uploaded_image(client, url):
    result = await client.post('/admin/teaching-tips', json={**BODY, 'cover_url': url})
    assert result.status_code == 422
