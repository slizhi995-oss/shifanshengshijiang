"""High-school biology follows the printed chapter / section / column hierarchy."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_biology import highschool_biology_directory
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_units import group_chapter_directory
from test_textbook_pipeline import environment, CHAPTER_TEXT


DIGEST = 'b02fac36b03bce0898410915fb4abecb3f62f287ee9aafb776f7b758b06806c6'


@pytest.mark.parametrize('title', ['附录', '附录1 培养基', '附 录Ⅱ 常用试剂', '１２．附 录3 电泳试剂'])
def test_appendices_are_removed_only_for_highschool_biology(title):
    assert is_removed_chapter('生物', title, '高中')
    assert is_removed_chapter('生物', title, '高中二年级')
    assert not is_removed_chapter('生物', title, '初中')
    assert not is_removed_chapter('语文', title, '高中')
    assert not is_removed_chapter('生物', '第1节 细胞的结构', '高中')


def reference_rows():
    return [dict(id=index, book_id=1, title=title, parent_title='', start_page=page,
                 end_page=page, printed_pages=str(page), content=CHAPTER_TEXT, is_published=True)
            for index, (title, page) in enumerate([
                ('第 1 章  走近细胞', 10), ('第 1 节 细胞是生命活动的基本单位', 11),
                ('第 2 节 细胞的多样性和统一性', 18),
                ('探究・实践 使用高倍显微镜观察几种细胞', 18),
                ('生物科技进展 人工合成生命的探索', 21)], 1)]


def test_reference_orders_same_page_entries_and_preserves_source_records():
    rows = reference_rows()
    before = deepcopy(rows)
    result = group_chapter_directory(SimpleNamespace(subject='生物', grade='高中', sha256=DIGEST),
                                     list(reversed(rows)))
    assert rows == before
    assert [row['id'] for row in result] == [1, 2, 3, 4, 5]
    assert [row['title'] for row in result] == [
        '第1章 走近细胞', '第1节 细胞是生命活动的基本单位', '第2节 细胞的多样性和统一性',
        '探究·实践 使用高倍显微镜观察几种细胞', '生物科技进展 人工合成生命的探索']
    assert [row['is_nested'] for row in result] == [False, False, False, True, True]
    assert result[3]['parent_title'] == result[4]['parent_title'] == result[2]['title']
    assert all(row['unit_title'] == '' for row in result)
    for old, new in zip(rows, result):
        for field in ('id', 'book_id', 'start_page', 'end_page', 'content', 'is_published'):
            assert old[field] == new[field]


def test_new_chapter_intro_and_appendix_reset_previous_section():
    rows = reference_rows() + [dict(id=index, title=title, start_page=page)
        for index, (title, page) in enumerate([
            ('第2章 细胞工程', 30), ('科技探索之路 细胞工程的发展历程', 31),
            ('第1节 植物细胞工程', 32), ('一 植物细胞工程的基本技术', 32),
            ('探究・实践 菊花的组织培养', 33), ('附录1 培养基的配制', 34)], 6)]
    result = highschool_biology_directory(SimpleNamespace(sha256='biology-no-review'), list(reversed(rows)))
    assert not result[6]['is_nested']
    assert result[6]['parent_title'] == result[5]['title']
    assert result[8]['is_nested'] and result[9]['is_nested']
    assert not result[-1]['is_nested'] and result[-1]['parent_title'] == ''


@pytest.mark.asyncio
async def test_student_api_exposes_highschool_biology_hierarchy(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='必修一', subject='生物', grade='高中', sha256=DIGEST,
                        original_filename='高中生物必修一.pdf', file_path='missing-biology.pdf',
                        page_count=30, is_published=True)
        db.add(book)
        await db.flush()
        for row in reversed(reference_rows()):
            db.add(TextbookChapter(book_id=book.id, **{k: v for k, v in row.items() if k not in ('id', 'book_id')}))
        appendix = TextbookChapter(book_id=book.id, title='附录1 培养基的配方', parent_title='',
                                   start_page=25, end_page=26, content=CHAPTER_TEXT, is_published=True)
        db.add(appendix)
        await db.commit()
        identifier = book.id
        appendix_id = appendix.id
    response = await client.get(f'/textbooks/{identifier}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert len(rows) == 5
    assert rows[0]['title'] == '第1章 走近细胞'
    assert rows[3]['title'] == '探究·实践 使用高倍显微镜观察几种细胞'
    assert rows[3]['is_nested'] and rows[4]['is_nested']
    assert (await client.get(f'/textbooks/chapters/{appendix_id}')).status_code == 404
    async with sessions() as db:
        original = await db.get(TextbookChapter, rows[0]['id'])
        assert original.title == '第 1 章  走近细胞' and original.parent_title == ''
