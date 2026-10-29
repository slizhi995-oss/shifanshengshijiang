"""Junior biology preserves source entries and displays their original hierarchy."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_biology import biology_directory_title, junior_biology_directory
from test_textbook_pipeline import environment, CHAPTER_TEXT


@pytest.mark.parametrize('original,expected', [
    ('第一节. 植物的生殖', '第一节 植物的生殖'),
    ('第二节． 昆虫的生殖和发育', '第二节 昆虫的生殖和发育'),
    ('科学·技术·社会  植物的组织培养', '科学·技术·社会 植物的组织培养'),
    ('第一章  生物的生殖和发育......2', '第一章 生物的生殖和发育'),
])
def test_source_labels_have_no_leaders_pages_or_extra_heading_dots(original, expected):
    assert biology_directory_title(original) == expected


def reference_rows():
    return [dict(id=index, book_id=1, title=title, parent_title='', start_page=page,
                 end_page=page, printed_pages=str(page), content=CHAPTER_TEXT, is_published=True)
            for index, (title, page) in enumerate([
                ('第七单元 生物圈中生命的延续和发展', 1),
                ('第一章  生物的生殖和发育', 2), ('第一节. 植物的生殖', 2),
                ('科学·技术·社会  植物的组织培养', 8), ('第二节. 昆虫的生殖和发育', 9),
                ('与生物学有关的职业  标本员', 13), ('第三节. 两栖动物的生殖和发育', 14),
                ('第四节. 鸟的生殖和发育', 18), ('科学·技术·社会  带你参观养鸡场', 22)], 1)]


def test_reference_preserves_all_entries_and_nests_columns_below_their_own_sections():
    rows = reference_rows()
    before = deepcopy(rows)
    output = junior_biology_directory(SimpleNamespace(sha256='biology-example'), list(reversed(rows)))
    assert rows == before
    assert [row['id'] for row in output] == list(range(1, 10))
    assert [row['title'] for row in output[1:]] == [
        '第一章 生物的生殖和发育', '第一节 植物的生殖', '科学·技术·社会 植物的组织培养',
        '第二节 昆虫的生殖和发育', '与生物学有关的职业 标本员',
        '第三节 两栖动物的生殖和发育', '第四节 鸟的生殖和发育', '科学·技术·社会 带你参观养鸡场']
    assert [row['id'] for row in output if row['is_nested']] == [4, 6, 9]
    assert [output[i]['parent_title'] for i in (3, 5, 8)] == [
        '第一节 植物的生殖', '第二节 昆虫的生殖和发育', '第四节 鸟的生殖和发育']
    assert all(output[i]['parent_title'] == '第一章 生物的生殖和发育' for i in (2, 4, 6, 7))
    for old, new in zip(rows, output):
        for field in ('id', 'book_id', 'start_page', 'end_page', 'printed_pages', 'content', 'is_published'):
            assert old[field] == new[field]


def test_new_units_projects_and_appendices_reset_the_previous_section():
    rows = reference_rows() + [dict(id=index, book_id=1, title=title, parent_title='', start_page=page)
        for index, (title, page) in enumerate([
            ('综合实践项目 制作模型', 23), ('第八单元 健康地生活', 24),
            ('第二章 用药与急救', 25), ('科学家的故事 李时珍与《本草纲目》', 26),
            ('附录 常见食物成分表', 27)], 10)]
    output = junior_biology_directory(SimpleNamespace(sha256='biology-resets'), rows)
    assert output[9]['parent_title'] == output[0]['title']
    assert not output[9]['is_nested']
    assert output[12]['parent_title'] == '第二章 用药与急救'
    assert output[12]['is_nested']
    assert output[-1]['parent_title'] == output[-1]['unit_title'] == ''


@pytest.mark.asyncio
async def test_student_api_exposes_biology_hierarchy_and_keeps_source_records(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='八年级下册', subject='生物', grade='初中八年级',
                        original_filename='初中生物八年级下册.pdf', file_path='missing-biology.pdf',
                        sha256='biology-api-fixture', page_count=30, is_published=True)
        db.add(book)
        await db.flush()
        for row in reversed(reference_rows()):
            data = {key: value for key, value in row.items() if key not in ('id', 'book_id')}
            db.add(TextbookChapter(book_id=book.id, **data))
        await db.commit()
        identifier = book.id
    response = await client.get(f'/textbooks/{identifier}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert len(rows) == 9
    assert rows[1]['title'] == '第一章 生物的生殖和发育'
    assert rows[2]['title'] == '第一节 植物的生殖'
    assert rows[3]['parent_title'] == rows[2]['title'] and rows[3]['is_nested']
    async with sessions() as db:
        original = await db.get(TextbookChapter, rows[2]['id'])
        assert original.title == '第一节. 植物的生殖'
        assert original.parent_title == ''
