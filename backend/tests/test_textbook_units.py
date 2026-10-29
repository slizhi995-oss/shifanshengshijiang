"""Unit headings without page numbers and existing reviewed chapter directories."""
from types import SimpleNamespace

import pytest

from app.services import textbook_units as units
from test_textbook_pipeline import environment, import_reviewed, ADMIN, CHAPTER_TEXT


def line(text, y, x=40, right=560):
    return dict(text=text, x=x, right=right, y=y, top=y-8, size=14)


def test_directory_units_without_pages_keep_theme_and_first_lesson_page():
    rows = [line('第一单元·识字', 50), line('1 天地人 ........ 8', 90),
            line('2 金木水火土 ........ 9', 120), line('第二单元·汉语拼音', 170),
            line('1 a o e ........ 20', 210)]
    assert units.directory_units(rows, 600, 840) == [
        dict(title='第一单元·识字', printed=8), dict(title='第二单元·汉语拼音', printed=20)]


def test_directory_units_join_detached_theme():
    rows = [line('第一单元', 50), line('中华人民共和国成立和社会主义制度建立', 80),
            line('第1课 中华人民共和国成立 ........ 4', 110)]
    assert units.directory_units(rows, 600, 840) == [
        dict(title='第一单元 中华人民共和国成立和社会主义制度建立', printed=4)]


def test_directory_units_read_both_columns():
    rows = [line('第一单元·阅读', 50, 40, 230), line('1 小蝌蚪找妈妈 .... 1', 90, 40, 230),
            line('第二单元·识字', 170, 40, 230), line('1 场景歌 .... 16', 210, 40, 230),
            line('第三单元·阅读', 50, 320, 570), line('4 彩虹 .... 28', 90, 320, 570)]
    assert units.directory_units(rows, 600, 840) == [
        dict(title='第一单元·阅读', printed=1), dict(title='第二单元·识字', printed=16),
        dict(title='第三单元·阅读', printed=28)]


def test_complete_unit_theme_uses_cover_boundary_and_appendices_are_separate(monkeypatch):
    monkeypatch.setattr(units, 'reviewed_directory', lambda _: {'offset': 5})
    monkeypatch.setattr(units, 'source_units', lambda *_: [
        dict(title='第一单元', printed=1), dict(title='第一单元 走进化学世界', printed=2),
        dict(title='第二单元 空气和氧气', printed=10)])
    book = SimpleNamespace(sha256='fixture', file_path='missing.pdf')
    chapters = [dict(id=index, title=title, start_page=page, printed_pages='', parent_title='')
                for index, (title, page) in enumerate([
                    ('第一单元', 6), ('课题1 物质的变化', 7), ('第二单元 空气和氧气', 15),
                    ('课题1 我们周围的空气', 16), ('30. 附录I 仪器', 30)], 1)]
    rows = units.group_chapter_directory(book, chapters)
    assert [row['unit_title'] for row in rows] == [
        '第一单元 走进化学世界', '第一单元 走进化学世界',
        '第二单元 空气和氧气', '第二单元 空气和氧气', '']
    assert [row['is_unit'] for row in rows] == [True, False, True, False, False]
    assert 'unit_title' not in chapters[0]


def test_english_lessons_with_repeated_unit_prefix_remain_selectable():
    assert units.unit_title('Unit 1. Family') == 'Unit 1. Family'
    assert units.unit_title('Unit 1. Family · Lesson 2. Family Together') == ''


@pytest.mark.asyncio
async def test_chapters_api_returns_unit_metadata_without_hiding_lessons(environment):
    client, _, _ = environment
    book, chapter, _, _ = await import_reviewed(client)
    response = await client.post(f'/textbooks/{book["id"]}/chapters', headers=ADMIN, json=dict(
        title='第一单元 运动与力', start_page=1, end_page=1, content=CHAPTER_TEXT, is_published=True))
    assert response.status_code == 201
    response = await client.get(f'/textbooks/{book["id"]}/chapters')
    assert response.status_code == 200
    rows = {row['id']: row for row in response.json()['data']}
    assert rows[chapter['id']]['unit_title'] == '第一单元 运动与力'
    assert rows[chapter['id']]['is_unit'] is False
    assert rows[response.json()['data'][-1]['id']]['is_unit'] is True
