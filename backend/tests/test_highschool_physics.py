"""High-school physics contains nonselectable headings and nested lessons."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.textbook import TextbookChapter
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_physics import highschool_physics_directory, physics_heading_title
from app.services.textbook_service import confirmed_chapter
from test_textbook_pipeline import environment, import_reviewed, ADMIN, CHAPTER_TEXT


@pytest.mark.parametrize('title', ['致同学们', '走进物理课堂之前', '序言 物理学：研究物质及其运动规律的科学',
    '前言', '课题研究', '学生实验', '索引', '学习资源'])
def test_supplements_are_excluded_only_from_highschool_physics(title):
    assert is_removed_chapter('物理', title, '高中一年级')
    assert not is_removed_chapter('物理', title, '初中八年级')
    assert not is_removed_chapter('政治', title, '高中一年级')


def test_heading_review_and_numbered_experiment_have_distinct_roles():
    titles = ['致同学们', '序言 物理学', '第一章 运动的描述 · 概述',
              '1 质点 参考系', '第一章 复习与提高', '第二章 匀变速直线运动的研究',
              '1 实验：探究小车速度随时间变化的规律', '课题研究', '学生实验', '索引']
    rows = highschool_physics_directory([dict(id=i, title=t, parent_title='') for i, t in enumerate(titles)])
    assert [r['title'] for r in rows] == [
        '第一章 运动的描述', '1 质点 参考系', '第一章 复习与提高',
        '第二章 匀变速直线运动的研究', '1 实验：探究小车速度随时间变化的规律']
    assert [r['is_unit'] for r in rows] == [True, False, False, True, False]
    assert [r['is_nested'] for r in rows] == [False, True, True, False, True]
    assert rows[2]['display_title'] == '复习与提高'
    assert rows[2]['parent_title'] == '第一章 运动的描述'
    assert physics_heading_title('第一章 复习与提高') == ''


@pytest.mark.asyncio
async def test_chapter_headers_are_not_recommended_or_accepted_for_generation(environment):
    client, sessions, _ = environment
    book, _, _, _ = await import_reviewed(client)
    ids = []
    async with sessions() as db:
        for title in ['致同学们', '第一章 运动的描述', '1 质点 参考系', '课题研究', '学生实验', '索引']:
            row = TextbookChapter(book_id=book['id'], title=title, start_page=2, end_page=2,
                                  content=CHAPTER_TEXT, is_published=True)
            db.add(row)
            await db.flush()
            ids.append(row.id)
        await db.commit()
        with pytest.raises(HTTPException) as error:
            await confirmed_chapter(db, ids[1])
        assert error.value.status_code == 422
        assert (await confirmed_chapter(db, ids[2]))[0].id == ids[2]
    response = await client.get(f'/textbooks/{book["id"]}/chapters')
    rows = response.json()['data']
    assert [r['id'] for r in rows] == ids[1:3]
    assert rows[0]['is_unit'] and not rows[1]['is_unit'] and rows[1]['is_nested']
    recommended = (await client.get('/textbooks/recommend', params={
        'subject': '物理', 'grade': book['grade'], 'book_id': book['id']})).json()['data']
    assert ids[1] not in [r['id'] for r in recommended]
    assert ids[2] in [r['id'] for r in recommended]
    assert not set(ids[3:]) & {r['id'] for r in recommended}
    for title in ['序言 物理学', '课题研究', '学生实验', '索引']:
        response = await client.post(f'/textbooks/{book["id"]}/chapters', headers=ADMIN, json=dict(
            title=title, start_page=2, end_page=2, content=CHAPTER_TEXT, is_published=True))
        assert response.status_code == 422
