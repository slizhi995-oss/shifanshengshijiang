"""Generation must extract real chapter pixels, including PDF vector diagrams."""
import asyncio
import io
import json
import zipfile
from types import SimpleNamespace

import fitz
import pytest
from PIL import Image
from sqlalchemy import select

from app.api.routes import ai
from app.models.ai_config import AIModelConfig
from app.models.textbook import TextbookAsset, TextbookChapter
from app.services import textbook_service as materials
from app.services import textbook_image_extraction as extraction
from app.services.lesson_materials import figure_tokens
from app.services.ai_model_service import DynamicAIService, _supports_dashscope_json_output
from test_textbook_pipeline import environment, ADMIN, generation_payload


QUOTE = 'Figure 1-1: A block resting on a horizontal surface.'


def test_mathematics_fullwidth_private_font_figure_numbers_are_canonical():
    source='图６．２\ue011２ 用两点表示直线；另见图６．２\ue011１２。'
    assert figure_tokens(source)=={'图6.2-2','图6.2-12'}
    assert figure_tokens('图 11 一 4 一 1')=={'图11-4-1'}
    figure=dict(bbox=[100,100,400,400],title='直线表示',figure_number='图6.2-2',
        description='直线经过A、B两点。',conditions='仅为直线表示示意。',tags=['直线'],source_quote='图6.2-2')
    assert extraction._checked_figures({'figures':[figure]},source)[0]['figure_number']=='图6.2-2'
    with pytest.raises(ValueError,match='Invented'):
        extraction._checked_figures({'figures':[{**figure,'figure_number':'图6.2-3'}]},source)
    assert extraction._quote_is_grounded('（第３题）','练习如下：\n（第３题）')
    assert not extraction._quote_is_grounded('（第４题）','练习如下：\n（第３题）')


def test_wrong_figure_number_can_retrieve_same_chapter_actual_object():
    item=dict(id='river',title='弯曲河道改直示意图',figure_number='',keywords=['河道'],description='弯曲河道和直线路径。')
    unrelated=dict(id='line',title='线段比较',figure_number='图6.2-12',keywords=['线段'],description='两条线段长度比较。')
    candidates=materials.search_assets([item,unrelated],'图6.2-12 弯曲河道与直线路径')
    assert [asset['id'] for asset in candidates]==['line','river']


def test_crop_keeps_caption_below_small_geometric_figure(tmp_path):
    source=tmp_path/'geometry.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page(width=600,height=800)
        page.draw_rect(fitz.Rect(100,200,180,260),fill=(0,0,.8))
        page.insert_text((100,315),'图6.2-2',fontname='china-s',fontsize=12)
        pdf.save(source)
    raw,width,height=extraction._crop(source,1,[150,240,350,335],'图6.2-2')
    assert height>300  # Both the drawing and its lower caption fit in the crop.
    with Image.open(io.BytesIO(raw)) as image:
        assert image.height==height


@pytest.mark.asyncio
async def test_native_qwen_vision_requests_structured_json(environment,monkeypatch):
    client,sessions,root=environment
    book,chapter=await setup_chapter(client,sessions)
    service=DynamicAIService()
    sent=[]
    async def completion(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"figures":[]}'),finish_reason='stop')],usage=None)
    async def get_client(config):
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
    monkeypatch.setattr(service,'_get_client',get_client)
    async with sessions() as db:
        config=(await db.execute(select(AIModelConfig).where(AIModelConfig.model_type=='vision'))).scalar_one()
        config.provider='dashscope';config.model_id='qwen3-vl-plus'
        config.api_base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
        await db.commit()
        assert _supports_dashscope_json_output(config)
        await service.chat_completion(db=db,user_id=1,model_type='vision',structured_output=True,
            messages=[{'role':'user','content':'Extract figures as JSON'}])
        assert sent[0]['response_format']=={'type':'json_object'}
        config.api_base_url='https://third-party.invalid/v1'
        assert not _supports_dashscope_json_output(config)


def test_source_evidence_accepts_pdf_punctuation_variants_without_accepting_paraphrase():
    base = {'bbox': [100, 100, 400, 400], 'title': 'Lewis', 'figure_number': '',
        'description': 'Lewis介绍自己的学校生活。', 'tags': ['Lewis', 'school day'],
        'conditions': '教材人物照片。'}
    checked = extraction._checked_figures(
        {'figures': [{**base, 'source_quote': "I'm Lewis. I'm from the UK."}]},
        'Hi! I’m Lewis. I’m from the UK. My school day starts at 8:30 a.m.')
    assert checked[0]['title'] == 'Lewis'
    combined = extraction._checked_figures(
        {'figures': [{**base, 'source_quote': "I’m Lewis. I’m from the UK. ... I’m Li Ming and I’m from China."}]},
        'Hi! I’m Lewis. I’m from the UK. School is fun. Hi! I’m Li Ming and I’m from China.')
    assert combined[0]['source_quote'].startswith('I’m Lewis')
    with pytest.raises(ValueError, match='evidence'):
        extraction._checked_figures(
            {'figures': [{**base, 'source_quote': 'Lewis enjoys an invented science lesson.'}]},
            'Hi! I’m Lewis. I’m from the UK. My school day starts at 8:30 a.m.')


def vector_pdf():
    with fitz.open() as pdf:
        for color in [(0, 0, .5), (0, .6, 0)]:
            page = pdf.new_page()
            page.insert_text((70, 80), QUOTE)
            page.draw_rect(fitz.Rect(130, 200, 220, 260), fill=color)
            page.draw_line((70, 260), (320, 260))
        return pdf.tobytes()


async def setup_chapter(client, sessions, vision=True):
    uploaded = await client.post('/textbooks', headers=ADMIN,
        files={'file': ('vector.pdf', vector_pdf(), 'application/pdf')},
        data={'title': 'Vector physics', 'subject': '物理', 'grade': '高中一年级'})
    assert uploaded.status_code == 201
    book = uploaded.json()['data']
    chapter = await client.post(f'/textbooks/{book["id"]}/chapters', headers=ADMIN,
        json={'title': '受力示意图', 'start_page': 1, 'end_page': 1, 'is_published': True})
    assert chapter.status_code == 201, chapter.text
    assert (await client.get(f'/textbooks/{book["id"]}/assets', headers=ADMIN)).json()['data'] == []
    if vision:
        async with sessions() as db:
            db.add(AIModelConfig(name='视觉测试', model_id='vision-stub', provider='openai',
                model_type='vision', api_key='test-only', is_enabled=True, is_default=True))
            await db.commit()
    return book, chapter.json()['data']


class Models:
    def __init__(self, failure=None):
        self.failure = failure
        self.events = []
        self.contexts = []
        self.vision_calls = 0

    async def generate_lesson_plan(self, **kwargs):
        self.events.append('generate')
        self.contexts.append(kwargs['textbook_context'])
        return '# 教学过程\n\n观察静止物体。\n\n[[图片：图1-1，观察静止物体与水平面]]'

    async def chat_completion(self, **kwargs):
        if kwargs['usage_type'] == 'textbook_image_extraction':
            assert 'generate' not in self.events
            self.events.append('extract')
            self.vision_calls += 1
            assert kwargs['model_type'] == 'vision'
            assert kwargs['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
            figure = {'title': '静止物体与水平面', 'figure_number': '',
                'description': '方块静止于水平面上。', 'tags': ['静止物体', '水平面'],
                'conditions': '示意图，不代表运动过程。', 'source_quote': QUOTE,
                'bbox': [90, 70, 670, 340]}
            if self.failure == 'bbox':
                figure['bbox'][2] = 1200
            if self.failure == 'quote':
                figure['source_quote'] = 'This sentence is invented.'
            return json.dumps({'figures': [figure]})
        if kwargs['usage_type'] == 'textbook_image_crop_review':
            assert 'generate' not in self.events
            self.events.append('review')
            self.vision_calls += 1
            assert kwargs['messages'][1]['content'][-1]['image_url']['url'].startswith('data:image/jpeg;base64,')
            assert sum(item['type']=='image_url' for item in kwargs['messages'][1]['content'])==2  # Original page plus actual crop.
            if self.failure == 'review-format':
                return '{"reviews":[]}'
            return json.dumps({'reviews': [{'index': 0, 'approved': self.failure != 'rejected',
                'complete': self.failure != 'rejected', 'matches_source': True, 'reason': '完整的方块与水平面示意图。'}]})
        self.events.append('select')
        tasks = json.loads(kwargs['messages'][1]['content'])
        return json.dumps({'selections': [{'index': task['index'], 'asset_id': task['candidates'][0]['id']} for task in tasks]})


@pytest.mark.asyncio
async def test_vector_figures_extracted_before_generation_private_bundle_and_cache(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter = await setup_chapter(client, sessions)
    stub = Models()
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', lambda: stub)
    # Ask by the actual depicted objects; the PDF fixture has an English caption.
    payload = generation_payload(chapter['id'])
    async def generate(**kwargs):
        await Models.generate_lesson_plan(stub, **kwargs)
        return '# 教学过程\n\n[[图片：静止物体与水平面，观察物体]]'
    stub.generate_lesson_plan = generate
    result = await client.post('/ai/generate', json=payload)
    assert result.status_code == 200, result.text
    data = result.json()['data']
    assert data['image_extraction'] == {'status': 'complete', 'extracted': 1}
    assert not data['material_warnings'] and len(data['asset_ids']) == 1
    identifier = data['asset_ids'][0]
    assert stub.events == ['extract', 'review', 'generate', 'select']
    assert [asset['id'] for asset in stub.contexts[0]['assets']] == [identifier]
    assert stub.contexts[0]['assets'][0]['description'] == '方块静止于水平面上。'
    picture = await client.get(f'/textbooks/assets/{identifier}/image')
    assert picture.status_code == 200
    with Image.open(io.BytesIO(picture.content)) as image:
        colors = image.convert('RGB').getdata()
        assert any(b > 100 and r < 20 and g < 20 for r, g, b in colors)
        assert not any(g > 100 and r < 20 and b < 20 for r, g, b in colors)  # Other chapter page is green.
    bundle = await client.get(f'/textbooks/lessons/{data["lesson_id"]}/bundle')
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert picture.content in [archive.read(name) for name in archive.namelist() if name.startswith('images/')]
    async with sessions() as db:
        assets = (await db.execute(select(TextbookAsset))).scalars().all()
        assert len(assets) == 1 and assets[0].pdf_page == 1 and assets[0].chapter_id == chapter['id']
        assert assets[0].conditions.startswith('[自动提取及视觉核对]')
    stub.events.clear()
    cached = (await client.post('/ai/generate', json=payload)).json()['data']
    assert cached['image_extraction']['status'] == 'cached' and stub.vision_calls == 2
    assert cached['asset_ids'] == [identifier]
    assert stub.events == ['generate', 'select']
    assert [asset['id'] for asset in stub.contexts[-1]['assets']] == [identifier]
    # A changed/withdrawn approval cannot be trusted from the filesystem cache.
    async with sessions() as db:
        row = (await db.execute(select(TextbookAsset))).scalar_one()
        row.is_reviewed = False
        await db.commit()
    stub.events.clear()
    withdrawn = (await client.post('/ai/generate', json=payload)).json()['data']
    assert withdrawn['asset_ids'] == [] and stub.vision_calls == 4
    assert stub.events == ['extract', 'review', 'generate']
    assert stub.contexts[-1]['assets'] == []
    assert (await client.get(f'/textbooks/assets/{identifier}/image')).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['bbox', 'quote', 'rejected', 'review-format', 'no-vision'])
async def test_invalid_or_unavailable_extraction_keeps_text_without_publishing(environment, monkeypatch, failure):
    client, sessions, root = environment
    book, chapter = await setup_chapter(client, sessions, vision=failure != 'no-vision')
    stub = Models(failure)
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', lambda: stub)
    result = await client.post('/ai/generate', json=generation_payload(chapter['id']))
    assert result.status_code == 200, result.text
    data = result.json()['data']
    assert '观察静止物体' in data['content'] and '图片待插入' in data['content']
    assert data['asset_ids'] == [] and data['material_warnings']
    async with sessions() as db:
        assert not (await db.execute(select(TextbookAsset))).scalars().all()


@pytest.mark.asyncio
async def test_rejected_crops_are_retried_instead_of_cached_as_complete(environment,monkeypatch):
    client,sessions,root=environment
    book,chapter=await setup_chapter(client,sessions)
    stub=Models('rejected')
    monkeypatch.setattr(ai,'get_dynamic_ai_service',lambda:stub)
    first=(await client.post('/ai/generate',json=generation_payload(chapter['id']))).json()['data']
    assert first['image_extraction']['status']=='partial' and not first['asset_ids']
    stub.failure=None;stub.events.clear()
    second=(await client.post('/ai/generate',json=generation_payload(chapter['id']))).json()['data']
    assert second['image_extraction']['status']=='complete' and len(second['asset_ids'])==1
    assert 'extract' in stub.events and 'review' in stub.events


@pytest.mark.asyncio
async def test_visual_review_can_correct_metadata_without_altering_picture(environment):
    client,sessions,root=environment
    book,chapter=await setup_chapter(client,sessions)
    class Correcting(Models):
        async def chat_completion(self,**kwargs):
            response=await super().chat_completion(**kwargs)
            if kwargs['usage_type']=='textbook_image_crop_review':
                data=json.loads(response)
                data['reviews'][0]['correction']=dict(title='水平面上的蓝色方块',
                    description='原图为蓝色方块静置在水平面上。',conditions='仅示意静止物体，不包含运动过程。')
                return json.dumps(data)
            return response
    async with sessions() as db:
        context=await materials.lesson_context(db,chapter['id'],'物理','高中一年级')
        result=await extraction.prepare_chapter_images(db.bind,Correcting(),1,context)
        assert result['status']=='complete'
        await db.commit()
        row=(await db.execute(select(TextbookAsset))).scalar_one()
        assert row.title=='水平面上的蓝色方块' and row.description=='原图为蓝色方块静置在水平面上。'


@pytest.mark.asyncio
async def test_text_generation_waits_for_extraction_to_finish(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter = await setup_chapter(client, sessions)
    entered, release, finished, generated = (asyncio.Event() for _ in range(4))
    async def pending(*args):
        entered.set()
        await release.wait()
        finished.set()
        return {'status': 'complete', 'extracted': 0, 'warnings': []}
    class Failed:
        async def generate_lesson_plan(self, **kwargs):
            assert finished.is_set()
            generated.set()
            raise RuntimeError('failed text generation')
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', Failed)
    monkeypatch.setattr(ai, 'prepare_chapter_images', pending)
    request = asyncio.create_task(client.post('/ai/generate', json=generation_payload(chapter['id'])))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await asyncio.sleep(0)
        assert not generated.is_set()
        release.set()
        result = await asyncio.wait_for(request, 2)
        assert result.status_code == 500 and finished.is_set() and generated.is_set()
    finally:
        request.cancel()
        await asyncio.gather(request, return_exceptions=True)


@pytest.mark.asyncio
async def test_chapter_changed_during_extraction_never_generates_text(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter = await setup_chapter(client, sessions)
    async def changed(*args):
        async with sessions() as db:
            row = await db.get(TextbookChapter, chapter['id'])
            row.content += '\nUpdated chapter content.'
            await db.commit()
        return {'status': 'complete', 'extracted': 0, 'warnings': []}
    class Forbidden:
        async def generate_lesson_plan(self, **kwargs):
            pytest.fail('Changed chapter must be rejected before text generation')
    monkeypatch.setattr(ai, 'get_dynamic_ai_service', Forbidden)
    monkeypatch.setattr(ai, 'prepare_chapter_images', changed)
    result = await client.post('/ai/generate', json=generation_payload(chapter['id']))
    assert result.status_code == 409


@pytest.mark.asyncio
async def test_page_timeout_preserves_completed_pages_and_retry_resumes(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter = await setup_chapter(client, sessions)
    edited = await client.put(f'/textbooks/chapters/{chapter["id"]}', headers=ADMIN,
        json={'title': chapter['title'], 'start_page': 1, 'end_page': 2, 'is_published': True})
    assert edited.status_code == 200
    calls = []
    async def page(*args):
        number = args[5]
        calls.append(number)
        if number == 2 and calls.count(2) == 1:
            await asyncio.Event().wait()
        return []
    monkeypatch.setattr(extraction, '_page_figures', page)
    monkeypatch.setattr(extraction, 'EXTRACTION_TIMEOUT', .5)
    async with sessions() as db:
        context = await materials.lesson_context(db, chapter['id'], '物理', '高中一年级')
        partial = await extraction.prepare_chapter_images(db.bind, None, 1, context)
        assert partial['status'] == 'partial' and partial['warnings']
        resumed = await extraction.prepare_chapter_images(db.bind, None, 1, context)
        assert resumed['status'] == 'complete' and not resumed['warnings']
        assert calls.count(1) == 1 and calls.count(2) == 2


@pytest.mark.asyncio
async def test_transient_page_failure_retries_before_generation(environment, monkeypatch):
    client, sessions, root = environment
    book, chapter = await setup_chapter(client, sessions)
    calls = []
    async def page(*args):
        number = args[5]
        calls.append(number)
        if calls.count(number) == 1:
            raise ValueError('temporary malformed provider response')
        return []
    monkeypatch.setattr(extraction, '_page_figures', page)
    async with sessions() as db:
        context = await materials.lesson_context(db, chapter['id'], '物理', '高中一年级')
        result = await extraction.prepare_chapter_images(db.bind, None, 1, context)
    assert result == {'status': 'complete', 'extracted': 0, 'warnings': []}
    assert calls == [1, 1]


@pytest.mark.asyncio
async def test_latest_numbered_crop_selected_without_breaking_historical_images(environment):
    client, sessions, root = environment
    book, chapter = await setup_chapter(client, sessions, vision=False)
    raw = io.BytesIO()
    Image.new('RGB', (240, 140), 'navy').save(raw, 'PNG')
    old = (await client.post(f'/textbooks/{book["id"]}/assets', headers=ADMIN,
        files={'file': ('old.png', raw.getvalue(), 'image/png')}, data={'pdf_page': 1})).json()['data']
    new = (await client.post(f'/textbooks/{book["id"]}/assets', headers=ADMIN,
        files={'file': ('new.png', raw.getvalue(), 'image/png')}, data={'pdf_page': 1})).json()['data']
    for item in [old, new]:
        response = await client.patch(f'/textbooks/assets/{item["asset_id"]}', headers=ADMIN, json={
            'title': '方块', 'chapter_id': chapter['id'], 'figure_number': '1-1' if item is old else '图1-1',
            'description': '水平面上的方块', 'tags': ['方块'], 'conditions': '[自动提取及视觉核对] 静止物体', 'is_reviewed': True})
        assert response.status_code == 200
    async with sessions() as db:
        context = await materials.lesson_context(db, chapter['id'], '物理', '高中一年级')
        assert [asset['id'] for asset in context['assets']] == [new['asset_id']]
        assert materials.search_assets(context['assets'], '图1-1，观察方块')[0]['id'] == new['asset_id']
    assert (await client.get(f'/textbooks/assets/{old["asset_id"]}/image')).status_code == 200
    async with sessions() as db:
        row = (await db.execute(select(TextbookAsset).where(TextbookAsset.asset_id == old['asset_id']))).scalar_one()
        row.conditions = '人工核对的完整图'
        await db.commit()
        context = await materials.lesson_context(db, chapter['id'], '物理', '高中一年级')
        assert [asset['id'] for asset in context['assets']] == [old['asset_id']]
