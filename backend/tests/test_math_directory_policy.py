"""Excluded maths supplements stay absent from APIs and import caches."""
import json
from pathlib import Path

import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import is_removed_math_chapter
from scripts.import_textbook_library import parse, PARSER_VERSION
from test_textbook_pipeline import environment, ADMIN, CHAPTER_TEXT


@pytest.mark.parametrize('title', ['小结', ' 小结 ', '数学活动', ' 数学活动… ', '复习题', '复习题21', '复习题２１', '复习参考题5 .', '部分中英文词汇索引'])
def test_only_requested_maths_supplements_are_excluded(title):
    assert is_removed_math_chapter('数学', title)
    assert not is_removed_math_chapter('物理', title)


@pytest.mark.parametrize('title', ['总复习', '9 总复习', '6 整理和复习', '复习与关联', '数学游戏', '综合与实践 低碳生活', '1.1 正数和负数'])
def test_regular_topics_remain_available(title):
    assert not is_removed_math_chapter('数学', title)


def test_import_cache_does_not_restore_removed_maths_chapters(tmp_path):
    cache = tmp_path / 'cache'
    cache.mkdir()
    chapters = [dict(title=title) for title in ['1.1 正数和负数', '小结', '数学活动', '复习参考题1', '部分中英文词汇索引', '总复习']]
    (cache / f'fixture-v{PARSER_VERSION}.json').write_text(json.dumps({'chapters': chapters}), encoding='utf-8')
    result = parse(Path('初中数学七年级上册.pdf'), 'fixture', tmp_path)
    assert [chapter['title'] for chapter in result['chapters']] == ['1.1 正数和负数', '总复习']
    other = parse(Path('初中物理八年级上册.pdf'), 'fixture', tmp_path)
    assert len(other['chapters']) == len(chapters)


@pytest.mark.asyncio
async def test_backend_rejects_and_omits_legacy_maths_supplements(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='数学测试', subject='数学', grade='初中七年级', edition='', volume='', publisher='',
                        file_path='missing-policy.pdf', original_filename='初中数学数学测试.pdf', sha256='math-policy-fixture',
                        page_count=100, status='ready', is_published=True)
        db.add(book)
        await db.flush()
        rows = [TextbookChapter(book_id=book.id, title=title, parent_title='', start_page=i, end_page=i,
                                printed_pages=str(i), content=CHAPTER_TEXT, is_published=True)
                for i, title in enumerate(['1.1 正数和负数', '小结', '数学活动', '复习题21', '部分中英文词汇索引', '9 总复习'], 1)]
        db.add_all(rows)
        await db.commit()
        identifier = book.id
        removed_id = rows[1].id
    for headers in ({}, ADMIN):
        response = await client.get(f'/textbooks/{identifier}/chapters', headers=headers)
        assert response.status_code == 200
        assert [row['title'] for row in response.json()['data']] == ['1.1 正数和负数', '9 总复习']
    assert (await client.get(f'/textbooks/chapters/{removed_id}')).status_code == 404
    assert (await client.get(f'/textbooks/chapters/{rows[2].id}')).status_code == 404
    response = await client.get('/textbooks/recommend', params={'subject': '数学', 'grade': '初中', 'topic': '小结'})
    assert {row['title'] for row in response.json()['data']} == {'1.1 正数和负数', '9 总复习'}
    for title in ['小结', '数学活动', '复习题21', '复习参考题1', '部分中英文词汇索引']:
        response = await client.post(f'/textbooks/{identifier}/chapters', headers=ADMIN,
                                    json=dict(title=title, start_page=1, end_page=1, content=CHAPTER_TEXT, is_published=True))
        assert response.status_code == 422
