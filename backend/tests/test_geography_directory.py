"""Source geography chapter hierarchy and omitted supplements."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_geography import geography_directory_title
from app.services.textbook_units import group_chapter_directory
from test_textbook_pipeline import environment, CHAPTER_TEXT


@pytest.mark.parametrize('title', ['跨学科主题学习 1 河流流域开发', '【跨学科主题学习】1 河流流域开发', '【跨学科主题学习】 1 河流流域开发'])
def test_junior_cross_subject_labels_have_one_pair_of_brackets(title):
    assert geography_directory_title(title, junior=True) == '【跨学科主题学习】 1 河流流域开发'


@pytest.mark.parametrize('title', ['主题活动六', '主题活动七', '主题活动八', '主题活动九'])
def test_junior_geography_theme_activities_are_removed(title):
    assert is_removed_chapter('地理', title, '初中七年级')
    assert not is_removed_chapter('地理', title, '高中')
    assert not is_removed_chapter('历史', title, '初中七年级')


@pytest.mark.parametrize('title', ['附录 地图图例', '附 录二 词汇表', '其他章节', '后记', '广东教育出版社有限公司'])
def test_geography_excludes_appendices_placeholders_and_publication_text(title):
    assert is_removed_chapter('地理', title, '初中七年级')
    assert is_removed_chapter('地理', title, '高中')
    assert not is_removed_chapter('语文', title, '高中')
    assert not is_removed_chapter('地理', '问题研究 火星基地应该是什么样子', '高中')


def test_audited_chapter_names_restore_hierarchy_without_changing_source_rows():
    rows = [dict(id=i, title=title, start_page=page, end_page=page, parent_title='')
            for i, (title, page) in enumerate([
                ('第一章', 6), ('第一节 地球的宇宙环境', 7),
                ('问题研究 火星基地应该是什么样子', 30)], 1)]
    original = deepcopy(rows)
    result = group_chapter_directory(SimpleNamespace(subject='地理', grade='高中',
        sha256='4cae01e59becda4c627006cfd745c399bb082605b00e068739e9abfca3fb3c13'), rows)
    assert result[0]['is_unit']
    assert result[0]['display_title'] == '第一章 宇宙中的地球'
    assert all(row['unit_title'] == '第一章 宇宙中的地球' for row in result)
    assert rows == original
    assert [row['id'] for row in result] == [1, 2, 3]


def test_standalone_chapters_and_columns_remain_selectable():
    rows = [dict(id=i, title=title, start_page=i) for i, title in enumerate([
        '第六章 发展与合作', '【跨学科主题学习】探索外来食料作物传播史',
        '第七章 北方地区', '第一节 自然特征与农业'], 1)]
    result = group_chapter_directory(SimpleNamespace(subject='地理', grade='初中', sha256='geography-test'), rows)
    assert not result[0]['is_unit'] and result[0]['unit_title'] == ''
    assert not result[1]['is_unit']
    assert result[2]['is_unit'] and result[3]['unit_title'] == '第七章 北方地区'


@pytest.mark.asyncio
async def test_student_api_exposes_geography_hierarchy_and_hides_appendices(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='测试地理', subject='地理', grade='初中七年级', sha256='geography-api',
                        original_filename='初中地理七年级上册.pdf', file_path='missing-geography.pdf',
                        page_count=30, is_published=True)
        db.add(book)
        await db.flush()
        for i, title in enumerate(['第一章 地球', '第一节 宇宙环境', '跨学科主题学习 1 河流流域开发', '附录一 词汇表', '主题活动六'], 1):
            row = TextbookChapter(book_id=book.id, title=title, parent_title='', start_page=i,
                                  end_page=i, content=CHAPTER_TEXT, is_published=True)
            db.add(row)
        await db.commit()
        identifier = book.id
        activity_id = row.id
    response = await client.get(f'/textbooks/{identifier}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert len(rows) == 3
    assert rows[0]['is_unit'] and all(row['unit_title'] == '第一章 地球' for row in rows)
    assert not rows[1]['is_unit'] and not rows[2]['is_unit']
    assert rows[2]['display_title'] == '【跨学科主题学习】 1 河流流域开发'
    assert (await client.get(f'/textbooks/chapters/{activity_id}')).status_code == 404
