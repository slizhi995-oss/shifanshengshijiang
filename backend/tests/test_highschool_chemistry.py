"""High-school chemistry follows only the main printed directory."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import fitz
import pytest
from fastapi import HTTPException

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_chemistry import chemistry_chapter_hierarchy, chemistry_heading_title
from app.services.textbook_outline import extract_outline, reviewed_directory
from app.services.textbook_service import confirmed_chapter
from scripts.import_textbook_library import parse, PARSER_VERSION
from test_textbook_pipeline import environment, ADMIN, CHAPTER_TEXT


BOOKS = [('高中化学必修一.pdf', 4, 18, (11, 18)), ('高中化学必修二.pdf', 4, 22, (7, 15)),
         ('高中化学选择性必修1.pdf', 4, 22, (9, 18)), ('高中化学选择性必修2.pdf', 3, 13, (9, 20)),
         ('高中化学选择性必修3.pdf', 5, 23, (9, 17))]


@lru_cache(maxsize=5)
def source_book(filename):
    path = Path(__file__).resolve().parents[2]/'教材'/'化学'/filename
    if not path.exists():
        pytest.skip('Local source textbook is not installed')
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    review = reviewed_directory(sha)
    with fitz.open(path) as document:
        pages, rows, _ = extract_outline(document, '化学', review['entries'], review['contents_pages'],
                                         review['offset'], grade='高中')
    return sha, review, pages, rows


@pytest.mark.parametrize('title', ['序言', '引言', '绪言', '绪论 化学与生活', '前言', '致同学们',
                                  '附录 名词索引', '１２．附 录Ⅰ 常数表', '元素周期表', '其他章节',
                                  '整理与提升', '探究 钠与水的反应', '方法导引 分类',
                                  '研究与实践 了解纯碱的生产历史', '化学与职业 水质检验员', '● 模型', '速率的因素'])
def test_highschool_prefaces_and_appendices_are_excluded(title):
    assert is_removed_chapter('化学', title, '高中一年级')
    assert not is_removed_chapter('政治', title, '高中')


@pytest.mark.parametrize('filename,headings,expected_rows,first_range', BOOKS)
def test_source_directory_contains_only_chapters_sections_and_experiments(filename, headings, expected_rows, first_range):
    sha, review, pages, stored = source_book(filename)
    rows = chemistry_chapter_hierarchy(stored, review=review, display=True)
    assert sum(row['is_unit'] for row in rows) == headings
    assert len(rows) == expected_rows
    assert not any(row['is_nested'] for row in rows)
    assert rows[0]['is_unit']
    first = next(row for row in rows if row['title'].startswith('第一节'))
    assert (first['start_page'], first['end_page']) == first_range
    assert all(not is_removed_chapter('化学', row['title'], '高中') for row in rows)
    assert all(row['is_unit'] or row['unit_title'] for row in rows)
    appendix = min(entry['printed']+review['offset'] for entry in review['entries'] if entry['title'].startswith('附录'))
    for row in rows:
        assert row['end_page'] < appendix
        assert 40 <= len(row['content']) <= 48000
        assert chemistry_heading_title(row['title']) or row['title'].startswith(('第一节', '第二节', '第三节', '第四节', '第五节', '实验活动'))
        if not row['is_unit']:
            assert row['parent_title'] == row['unit_title']
    # Re-normalizing a cached parse cannot absorb appendix pages or change text.
    assert chemistry_chapter_hierarchy(stored, pages, review) == stored
    assert all('is_unit' not in row for row in stored)


def test_sodium_and_chlorine_chapter_matches_the_users_reference_exactly():
    _, _, _, rows = source_book('高中化学必修一.pdf')
    start = next(i for i, row in enumerate(rows) if row['title'].startswith('第二章'))
    end = next(i for i, row in enumerate(rows) if row['title'].startswith('第三章'))
    assert [row['title'] for row in rows[start:end]] == [
        '第二章 海水中的重要元素——钠和氯',
        '第一节 钠及其化合物', '第二节 氯及其化合物', '第三节 物质的量',
        '实验活动1 配制一定物质的量浓度的溶液']


def test_old_import_cache_is_repaired_with_the_reviewed_labels(tmp_path):
    filename = '高中化学选择性必修1.pdf'
    sha, review, pages, _ = source_book(filename)
    raw = [dict(title='引言', start_page=6, end_page=7, content='old', parent_title=''),
           dict(title='第一章 化学反应的热效应', start_page=8, end_page=8, content='old', parent_title=''),
           dict(title='第一节 反应热', start_page=9, end_page=9, content='old', parent_title=''),
           dict(title='探究 ● 中和反应反应热的测定', start_page=10, end_page=16, content='old', parent_title=''),
           dict(title='第二节 反应热的计算', start_page=19, end_page=24, content='old', parent_title=''),
           dict(title='整理与提升', start_page=25, end_page=27, content='old', parent_title='')]
    cache = tmp_path/'cache'
    cache.mkdir()
    (cache/f'{sha}-v{PARSER_VERSION}.json').write_text(json.dumps(dict(chapters=raw, pages=pages)), encoding='utf8')
    rows = parse(Path(filename), sha, tmp_path)['chapters']
    assert rows[0]['title'].startswith('第一章')
    assert rows[1]['end_page'] == 18
    assert [row['title'] for row in rows] == ['第一章 化学反应的热效应', '第一节 反应热', '第二节 反应热的计算']


@pytest.mark.asyncio
async def test_api_uses_chapter_groups_and_blocks_headers_and_removed_rows_for_generation(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='必修一', subject='化学', grade='高中', original_filename='高中化学必修一.pdf',
                        file_path='missing.pdf', sha256='chemistry-api', page_count=20, is_published=True)
        db.add(book)
        await db.flush()
        rows = [TextbookChapter(book_id=book.id, title=title, parent_title='', start_page=i, end_page=i,
                                printed_pages=str(i), content=CHAPTER_TEXT, is_published=True)
                for i, title in enumerate(['绪言', '第一章 物质及其变化', '第一节 物质的分类及转化',
                    '方法导引 分类', '整理与提升', '附录 名词索引'], 1)]
        db.add_all(rows)
        await db.commit()
        book_id = book.id
        ids = [row.id for row in rows]
        for identifier in (ids[0], ids[1], ids[3], ids[4], ids[-1]):
            with pytest.raises(HTTPException) as error:
                await confirmed_chapter(db, identifier)
            assert error.value.status_code == 422
        assert (await confirmed_chapter(db, ids[2]))[0].id == ids[2]
    response = await client.get(f'/textbooks/{book_id}/chapters')
    rows = response.json()['data']
    assert [row['id'] for row in rows] == ids[1:3]
    assert [row['is_unit'] for row in rows] == [True, False]
    assert [row['is_nested'] for row in rows] == [False, False]
    assert rows[1]['parent_title'] == rows[0]['title']
    recommended = (await client.get('/textbooks/recommend', params={'subject': '化学', 'grade': '高中', 'book_id': book_id})).json()['data']
    assert {row['id'] for row in recommended} == {ids[2]}
    for title in ['引言', '序言', '附录 相对原子质量表', '整理与提升', '方法导引 分类']:
        response = await client.post(f'/textbooks/{book_id}/chapters', headers=ADMIN, json=dict(
            title=title, start_page=1, end_page=1, content=CHAPTER_TEXT, is_published=True))
        assert response.status_code == 422
