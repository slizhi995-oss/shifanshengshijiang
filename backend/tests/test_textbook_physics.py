"""Physics directories retain the printed chapter/section/review order."""
from types import SimpleNamespace

import pytest

from app.services.textbook_outline import contents_entries, reviewed_directory
from app.services.textbook_units import group_chapter_directory
from scripts.normalize_junior_physics import proposals
from test_textbook_pipeline import environment, import_reviewed, ADMIN, CHAPTER_TEXT


def test_slash_directory_joins_detached_chapter_without_the_neighboring_lesson():
    def line(text, x, y):
        return dict(text=text, x=x, right=x+150, y=y, top=y-8, size=14)
    lines = [line('第二章', 40, 100), line('机械运动 / 36', 40, 125),
             line('第一节 运动与静止 / 37', 200, 100),
             line('第二节 长度及其测量 / 41', 200, 125),
             line('整理与复习 / 66', 200, 150)]
    assert contents_entries(lines, 600, 840) == [
        dict(title='第二章 机械运动', printed=36), dict(title='第一节 运动与静止', printed=37),
        dict(title='第二节 长度及其测量', printed=41), dict(title='整理与复习', printed=66)]


def test_audited_eighth_grade_directory_matches_the_requested_example():
    review = reviewed_directory('215d0783bc882d57b763547b5164a2bc5db1fb7d85c6e998ea5bb5abb25b3be1')
    entries = [dict(id=i, title=e['title'], start_page=e['printed']+review['offset'], parent_title='')
               for i, e in enumerate(review['entries'])]
    rows = group_chapter_directory(SimpleNamespace(subject='物理', grade='初中八年级'), entries)
    block = [r for r in rows if r['unit_title'] == '第二章 机械运动']
    assert [r['title'] for r in block] == ['第二章 机械运动', '第一节 运动与静止', '第二节 长度及其测量',
        '第三节 比较物体运动的快慢', '第四节 平均速度', '第五节 平均速度的测量', '整理与复习']
    assert [r['is_unit'] for r in block] == [True, False, False, False, False, False, False]
    assert [r['is_nested'] for r in block] == [False, True, True, True, True, True, True]
    assert block[-1]['parent_title'] == '第二章 机械运动'
    assert not any(r['title'].startswith('附录') for r in rows)
    assert entries[0]['parent_title'] == ''  # Display formatting has no side effects.


def test_migration_preserves_named_chapter_id_and_is_repeatable(monkeypatch):
    from scripts import normalize_junior_physics as migration
    monkeypatch.setattr(migration, 'reviewed_directory', lambda _: dict(offset=7, entries=[
        dict(title='第二章 机械运动', printed=36), dict(title='第一节 运动与静止', printed=37),
        dict(title='整理与复习', printed=66)]))
    rows = [SimpleNamespace(id=i, title=title, parent_title='', start_page=page, is_published=True)
            for i, title, page in [(10, '机械运动', 43), (20, '第二章', 43),
                                   (30, '第一节 运动与静止', 44), (40, '整理与复习', 73)]]
    book = SimpleNamespace(sha256='fixture')
    changes, hidden = proposals(book, rows)
    assert hidden == [20]
    assert next(c for c in changes if c['field'] == 'title')['id'] == 10
    for change in changes:
        setattr(next(r for r in rows if r.id == change['id']), change['field'], change['after'])
    rows[1].is_published = False
    assert proposals(book, rows) == ([], [])


@pytest.mark.asyncio
async def test_physics_api_groups_chapter_and_review_without_changing_ids(environment):
    client, _, _ = environment
    book, _, _, _ = await import_reviewed(client)
    await client.patch(f'/textbooks/{book["id"]}', headers=ADMIN, json={
        key: '初中八年级' if key == 'grade' else book[key]
        for key in ('title', 'subject', 'grade', 'publisher', 'edition', 'volume')})
    identifiers = []
    for title in ['第二章 机械运动', '第一节 运动与静止', '整理与复习']:
        response = await client.post(f'/textbooks/{book["id"]}/chapters', headers=ADMIN, json=dict(
            title=title, start_page=2, end_page=2, content=CHAPTER_TEXT, is_published=True))
        assert response.status_code == 201
        identifiers.append(response.json()['data']['id'])
    rows = (await client.get(f'/textbooks/{book["id"]}/chapters')).json()['data'][-3:]
    assert [r['id'] for r in rows] == identifiers
    assert [r['is_unit'] for r in rows] == [True, False, False]
    assert [r['is_nested'] for r in rows] == [False, True, True]
    assert all(r['unit_title'] == '第二章 机械运动' for r in rows)
    assert rows[-1]['parent_title'] == '第二章 机械运动'


@pytest.mark.parametrize('subject,title,expected', [
    ('物理', '附录', True), ('物理', '附录 本册书中用到的物理量及其单位', True),
    ('物理', '12. 附录A 常用物理量', True), ('物理', '  附 录  常量', True),
    ('物理', '整理与复习', False), ('物理', '第一节 运动与静止', False),
    ('化学', '附录 实验器材', False), ('数学', '附录 常量', False),
])
def test_physics_appendix_exclusion(subject, title, expected):
    from app.services.textbook_catalog import is_removed_physics_appendix
    assert is_removed_physics_appendix(subject, title) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('grade', ['初中八年级', '高中一年级'])
async def test_physics_appendices_cannot_be_listed_selected_or_reimported(environment, grade):
    from app.models.textbook import Textbook, TextbookChapter
    from app.services.textbook_service import confirmed_chapter
    from fastapi import HTTPException
    client, sessions, _ = environment
    book, _, _, _ = await import_reviewed(client)
    async with sessions() as db:
        stored = await db.get(Textbook, book['id'])
        stored.grade = grade
        appendix = TextbookChapter(book_id=book['id'], title='附录 常用物理量',
            start_page=2, end_page=2, content=CHAPTER_TEXT, is_published=True)
        db.add(appendix)
        await db.commit()
        appendix_id = appendix.id
        with pytest.raises(HTTPException) as error:
            await confirmed_chapter(db, appendix_id)
        assert error.value.status_code == 422
    for headers in ({}, ADMIN):
        response = await client.get(f'/textbooks/{book["id"]}/chapters', headers=headers)
        assert appendix_id not in [r['id'] for r in response.json()['data']]
        assert (await client.get(f'/textbooks/chapters/{appendix_id}', headers=headers)).status_code == 404
    recommendations = (await client.get('/textbooks/recommend', params={
        'subject': '物理', 'grade': grade, 'topic': '附录'})).json()['data']
    assert appendix_id not in [r['id'] for r in recommendations]
    response = await client.post(f'/textbooks/{book["id"]}/chapters', headers=ADMIN, json=dict(
        title='附录 常用物理量', start_page=2, end_page=2, content=CHAPTER_TEXT, is_published=True))
    assert response.status_code == 422


def test_import_cache_does_not_restore_physics_appendices(tmp_path):
    import json
    from scripts.import_textbook_library import parse, PARSER_VERSION
    from pathlib import Path
    cache = tmp_path/'cache'
    cache.mkdir()
    (cache/f'fixture-v{PARSER_VERSION}.json').write_text(json.dumps(dict(chapters=[
        dict(title='附录 物理量'), dict(title='整理与复习')])), encoding='utf-8')
    result = parse(Path('高中物理必修第一册.pdf'), 'fixture', tmp_path)
    assert [c['title'] for c in result['chapters']] == ['整理与复习']
