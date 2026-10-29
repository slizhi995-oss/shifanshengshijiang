"""Audio import integrity, version/unit isolation, generation, and owned playback."""
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import ai, resources
from app.core.deps import get_current_user, get_db
from app.models import Base
from app.models.audio_resource import AudioLesson, AudioResource, AudioVectorIndex
from app.models.textbook import Textbook, TextbookChapter, TextbookLesson
from app.models.user import User, UserRole
from app.services import audio_resources as service
from app.services.audio_vectors import cosine, fit_idf, vectorize


def test_persistable_vectors_and_unit_namespaces():
    documents = ['school playground classroom 学校', 'family father mother 家庭']
    idf = fit_idf(documents)
    assert cosine(vectorize('school playground 学校', idf), vectorize(documents[0], idf)) > .8
    assert cosine(vectorize(documents[0], idf), vectorize(documents[1], idf)) == 0
    assert service.unit_key('Starter Unit 1 Hello!') != service.unit_key('Unit 1 You and Me')
    assert service.unit_key('Welcome Unit · Listening') == ('welcomeunit', 0)
    assert service.volume_key('必修二') == service.volume_key('必修第二册')
    assert service.volume_key('选择性必修二') != service.volume_key('必修二')
    assert service.printed_page_numbers('2-3, 7') == {2, 3, 7}
    assert service.unit_signature('Workbook Unit 1') is None


@pytest_asyncio.fixture
async def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(service.settings, 'AUDIO_SOURCE_DIR', str(tmp_path / 'audio'))
    monkeypatch.setattr(service.settings, 'TEXTBOOK_STORAGE_DIR', str(tmp_path / 'books'))
    monkeypatch.setattr(service.settings, 'AI_ENABLED', True)
    root = service.audio_root()
    (root / 'metadata').mkdir(parents=True)
    (root / 'book').mkdir()
    records = []
    for identifier, digest, unit_type, number, eligible in [
        ('audio-correct', 'a' * 64, 'Unit', 1, True),
        ('audio-vocabulary', 'a' * 64, 'Unit', 1, True),
        ('audio-starter', 'a' * 64, 'StarterUnit', 1, True),
        ('audio-other-unit', 'a' * 64, 'Unit', 2, True),
        ('audio-other-edition', 'b' * 64, 'Unit', 1, True),
        ('audio-unreviewed', 'a' * 64, 'Unit', 1, False),
        ('audio-broken', 'a' * 64, 'Unit', 1, True),
    ]:
        data = (identifier * 15).encode()
        relative = f'book/{identifier}.mp3'
        (root / relative).write_bytes(data)
        records.append(dict(resource_id=identifier, relative_new=relative,
            sha256=hashlib.sha256(data).hexdigest() if identifier != 'audio-broken' else '0' * 64,
            subject='英语', stage='初中', series='人教版', volume='七年级上册', textbook_sha256=digest,
            unit_type=unit_type, unit_number=number, unit_title=f'{unit_type} {number} My School',
            section='Section A', activity_id='1b', audio_kind='词汇' if 'vocabulary' in identifier else '听力',
            printed_page=None if 'vocabulary' in identifier else 20, pdf_page=None if 'vocabulary' in identifier else 28,
            eligible_for_automatic_recommendation=eligible, search_text='My school classroom playground listen school activities',
            textbook_excerpt='Listen to the school conversation.', size_bytes=len(data), audio_content_verified=False))
    manifest = root / 'metadata' / '音频检索元数据.jsonl'
    manifest.write_text('\n'.join(json.dumps(record) for record in records), encoding='utf8')

    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with sessions() as db:
        db.add_all([User(id=i, user_code=str(i), name='测试学生', password_hash='unused', role=UserRole.STUDENT) for i in (1, 2)])
        db.add(Textbook(id=1, title='七年级上册', subject='英语', grade='初中七年级', edition='人教版',
            volume='七年级上册', file_path='private.pdf', original_filename='book.pdf', sha256='a' * 64, is_published=True))
        await db.flush()
        db.add(TextbookChapter(id=1, book_id=1, title='Listening: School activities', parent_title='Unit 1 My School · Section A',
            start_page=28, end_page=28, printed_pages='20', content='My school classroom playground activities', is_published=True))
        await db.flush()
        db.add(TextbookLesson(id=1, user_id=1, chapter_id=1, title='My School', content='My school classroom playground activities',
            sources_json=json.dumps({'book_title': '七年级上册', 'chapter_title': 'My School'})))
        await db.commit()
        report = await service.import_audio_catalog(db)
        assert report['total'] == 7 and report['indexed'] == 5
        assert report['pending_review'] == 1 and report['unavailable'] == 1

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
    app.include_router(ai.router, prefix='/ai')
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'x-user': '1'}) as client:
        yield client, sessions, root
    await engine.dispose()


@pytest.mark.asyncio
async def test_import_idempotency_version_unit_review_boundaries_and_files(environment):
    client, sessions, root = environment
    async with sessions() as db:
        await service.import_audio_catalog(db)
        assert (await db.execute(select(func.count(AudioResource.id)))).scalar_one() == 7
        assert (await db.execute(select(func.count(AudioLesson.id)))).scalar_one() == 1
    result = (await client.get('/resources/audio-lessons')).json()
    assert result['total'] == 1
    lesson_id = result['items'][0]['id']
    detail = (await client.get(f'/resources/audio-lessons/{lesson_id}')).json()
    assert detail['content'] == 'My school classroom playground activities'
    assert {item['resource_id'] for item in detail['audios']} == {'audio-correct', 'audio-vocabulary'}
    assert detail['audios'][0]['resource_id'] == 'audio-correct'  # Exact page precedes unit vocabulary.
    assert str(root) not in json.dumps(detail) and 'sha256' not in json.dumps(detail)
    assert detail['audios'][0]['audio_content_verified'] is False
    assert (await client.get('/resources/audio-lessons', headers={'x-user': '2'})).json()['total'] == 0
    assert (await client.get(f'/resources/audio-lessons/{lesson_id}', headers={'x-user': '2'})).status_code == 404
    assert (await client.get(f'/resources/audio-lessons/{lesson_id}', headers={'x-user': ''})).status_code == 401
    path = f'/resources/audio-lessons/{lesson_id}/audio/audio-correct/file'
    assert (await client.get(path, headers={'x-user': '2'})).status_code == 404
    assert (await client.get(path.replace('audio-correct', 'audio-unreviewed'))).status_code == 404
    assert (await client.get(path.replace('audio-correct', 'audio-other-edition'))).status_code == 404
    response = await client.get(path, headers={'range': 'bytes=2-9'})
    assert response.status_code == 206 and response.content == (root / 'book/audio-correct.mp3').read_bytes()[2:10]
    assert response.headers['content-type'] == 'audio/mpeg' and 'no-store' in response.headers['cache-control']
    assert (await client.get(path, headers={'range': 'bytes=9999-'})).status_code == 416
    assert (await client.get(path, headers={'range': 'bytes=-0'})).status_code == 416
    (root / 'book/audio-correct.mp3').write_bytes(b'changed')
    assert (await client.get(path)).status_code == 409
    (root / 'book/audio-correct.mp3').unlink()
    assert (await client.get(path)).status_code == 410


@pytest.mark.asyncio
async def test_generation_automatically_persists_matches_and_generic_empty_states(environment, monkeypatch):
    client, sessions, _ = environment

    async def generate(**kwargs):
        return '# My School\nSchool classroom playground activities. Listen to the school conversation.'

    monkeypatch.setattr(ai, 'get_dynamic_ai_service', lambda: SimpleNamespace(generate_lesson_plan=generate))
    response = await client.post('/ai/generate', json=dict(subject='英语', grade='初中七年级', topic='My School',
        use_textbook=True, textbook_chapter_id=1, stream=False))
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['lesson_id'] and data['resource_lesson_id'] and data['audio_count'] == 2
    detail = (await client.get(f'/resources/audio-lessons/{data["resource_lesson_id"]}')).json()
    assert detail['source']['chapter_title'] == 'Listening: School activities'
    assert len(detail['audios']) == 2
    # General generation has a server-side resource record as well.
    general = await client.post('/ai/generate', json=dict(subject='英语', grade='初中七年级', topic='My School', stream=False))
    assert general.status_code == 200 and general.json()['data']['resource_lesson_id']
    async with sessions() as db:
        unrelated = await service.save_audio_lesson(db, 1, 'A very different topic', '英语', '高中', 'Listening exercise')
        physics = await service.save_audio_lesson(db, 1, '惯性', '物理', '高中', '牛顿第一定律')
        other_edition = await service.save_audio_lesson(db, 1, 'My School', '英语', '初中七年级', 'My school',
            {'textbook_sha256': 'c' * 64, 'chapter_title': 'Unit 1 My School'})
        assert unrelated.match_status == 'no_match' and unrelated.matches_json == '[]'
        assert physics.match_status == 'unsupported_subject' and physics.matches_json == '[]'
        assert other_edition.match_status == 'edition_unavailable' and other_edition.matches_json == '[]'


@pytest.mark.asyncio
async def test_import_rejects_path_escape_before_mutating_catalog(environment):
    _, sessions, root = environment
    manifest = root / 'metadata/音频检索元数据.jsonl'
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf8').splitlines()]
    rows[0]['relative_new'] = '../outside.mp3'
    manifest.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf8')
    async with sessions() as db:
        with pytest.raises(ValueError, match='音频路径无效'):
            await service.import_audio_catalog(db)
        assert (await db.execute(select(func.count(AudioResource.id)))).scalar_one() == 7


@pytest.mark.asyncio
async def test_stream_generation_saves_resources_after_completion(environment, monkeypatch):
    client, sessions, _ = environment

    async def stream(**kwargs):
        yield '# My School\n'
        yield 'School classroom playground activities.'

    monkeypatch.setattr(ai, 'get_dynamic_ai_service', lambda: SimpleNamespace(generate_lesson_plan_stream=stream))
    response = await client.post('/ai/generate', json=dict(subject='英语', grade='初中七年级', topic='My School', stream=True))
    assert response.status_code == 200 and 'event: resources' in response.text
    assert response.text.endswith('data: [DONE]\n\n')
    async with sessions() as db:
        saved = (await db.execute(select(AudioLesson).where(AudioLesson.textbook_lesson_id.is_(None)))).scalar_one()
        assert 'playground' in saved.content and json.loads(saved.matches_json)


@pytest.mark.asyncio
async def test_same_curriculum_different_pdf_copy_and_stale_empty_cache(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        db.add(Textbook(id=2, title='七年级上册扫描件', subject='英语', grade='初中七年级', edition='人教版',
            volume='七年级上册', file_path='scan.pdf', original_filename='scan.pdf', sha256='c' * 64, is_published=True))
        db.add(Textbook(id=3, title='同名册次另一套教材', subject='英语', grade='初中七年级', edition='北师大版',
            volume='七年级上册', publisher='北京师范大学出版社', file_path='other.pdf', original_filename='other.pdf',
            sha256='d' * 64, is_published=True))
        await db.flush()
        for book_id, titles in [(2, ['Unit 1 My School', 'Unit 2 Family Life', 'Unit 3 Healthy Habits']),
                                (3, ['Unit 1 Family', 'Unit 2 School Life', 'Unit 3 Sports'])]:
            for number, title in enumerate(titles, 1):
                db.add(TextbookChapter(book_id=book_id, title=title, parent_title='', start_page=number * 10,
                    end_page=number * 10 + 9, printed_pages=str(number * 10), content=title, is_published=True))
        template = (await db.execute(select(AudioResource).where(AudioResource.resource_id == 'audio-correct'))).scalar_one()
        second_unit = (await db.execute(select(AudioResource).where(AudioResource.resource_id == 'audio-other-unit'))).scalar_one()
        second_unit.unit_title = 'UNIT 2 FAMILY LIFE'
        fields = {column.name: getattr(template, column.name) for column in AudioResource.__table__.columns
                  if column.name not in ('id', 'created_at', 'updated_at')}
        db.add(AudioResource(**{**fields, 'resource_id': 'audio-third-unit', 'unit_number': 3,
                               'unit_title': 'UNIT 3 HEALTHY HABITS'}))
        db.add(AudioResource(**{**fields, 'resource_id': 'audio-reading', 'section': 'Reading and Thinking',
                               'audio_kind': '课文朗读'}))
        await db.flush()
        context = dict(book_id=2, textbook_sha256='c' * 64, volume='七年级上册',
            chapter_title='Listening', parent_title='UNIT 1 MY SCHOOL', printed_pages='20',
            start_page=400, end_page=410)  # PDF page numbers are deliberately unrelated.
        lesson = await service.save_audio_lesson(db, 1, 'Listening', '英语', '初中七年级', 'School activities', context)
        matches = json.loads(lesson.matches_json)
        assert {item['resource_id'] for item in matches} == {'audio-correct', 'audio-vocabulary'}
        assert matches[0]['reason'] == '对应教材页的配套音频'
        # An old empty result must not survive a matching-rule update.
        lesson.matches_json, lesson.match_status = '[]', 'edition_unavailable'
        lesson.matched_version = (await db.get(AudioVectorIndex, 1)).version
        lesson_id = lesson.id
        wrong = await service.save_audio_lesson(db, 1, 'Listening', '英语', '初中七年级', 'School activities',
            {**context, 'book_id': 3, 'textbook_sha256': 'd' * 64})
        assert wrong.match_status == 'edition_unavailable' and wrong.matches_json == '[]'
        await db.commit()
    detail = (await client.get(f'/resources/audio-lessons/{lesson_id}')).json()
    assert detail['match_status'] == 'ready' and len(detail['audios']) == 2
    search = (await client.get('/resources/audio-lessons', params={'keyword': 'MY SCHOOL'})).json()
    assert lesson_id in {item['id'] for item in search['items']}
