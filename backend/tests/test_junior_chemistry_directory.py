"""Junior chemistry exclusions apply to import, selection and generation."""
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_service import confirmed_chapter
from scripts.import_textbook_library import parse, PARSER_VERSION
from test_textbook_pipeline import environment, ADMIN, CHAPTER_TEXT


EXCLUDED = ['其他章节', '绪论  化学使世界变得更加绚丽多彩', '整理与提高', '整理与提升',
            '复习与提高', '附录', '附录I 实验室常用仪器', '附录Ⅱ 相对原子质量表',
            '附录III 名词索引', '12. 附 录  溶解性表', '第七单元 整理与提升', '３．复习与提高']
RETAINED = ['第一单元 走进化学世界', '课题1 物质的变化和性质', '课题3 金属资源的利用和保护',
            '实验活动1 氧气的实验室制取与性质', '跨学科实践活动3 水质检测及自制净水器']


@pytest.mark.parametrize('title', EXCLUDED)
def test_only_junior_chemistry_supplements_are_excluded(title):
    assert is_removed_chapter('化学', title, '初中八年级')
    assert is_removed_chapter('化学', title, '初中')
    assert not is_removed_chapter('政治', title, '初中')


@pytest.mark.parametrize('title', RETAINED)
def test_lessons_experiments_and_cross_subject_activities_are_retained(title):
    assert not is_removed_chapter('化学', title, '初中九年级')


def test_cached_import_cannot_restore_excluded_entries(tmp_path):
    cache = tmp_path/'cache'
    cache.mkdir()
    (cache/f'chemistry-v{PARSER_VERSION}.json').write_text(
        json.dumps(dict(chapters=[dict(title=title) for title in EXCLUDED+RETAINED])), encoding='utf8')
    result = parse(Path('初中化学八年级全一册.pdf'), 'chemistry', tmp_path)
    assert [row['title'] for row in result['chapters']] == RETAINED


@pytest.mark.asyncio
async def test_api_hides_legacy_entries_and_blocks_selection_without_deleting_history(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='八年级全一册', subject='化学', grade='初中八年级',
                        original_filename='初中化学八年级全一册.pdf', file_path='missing-chemistry.pdf',
                        sha256='chemistry-policy-fixture', page_count=100, is_published=True)
        db.add(book)
        await db.flush()
        rows = [TextbookChapter(book_id=book.id, title=title, parent_title='', start_page=i, end_page=i,
                                printed_pages=str(i), content=CHAPTER_TEXT, is_published=True)
                for i, title in enumerate(EXCLUDED+RETAINED, 1)]
        db.add_all(rows)
        await db.commit()
        book_id = book.id
        ids = [row.id for row in rows[:len(EXCLUDED)]]
    for headers in ({}, ADMIN):
        response = await client.get(f'/textbooks/{book_id}/chapters', headers=headers)
        assert response.status_code == 200
        assert [row['title'] for row in response.json()['data']] == RETAINED
    response = await client.get('/textbooks/recommend', params={'subject': '化学', 'grade': '初中', 'topic': '复习'})
    assert {row['title'] for row in response.json()['data']} == set(RETAINED)
    for identifier in ids:
        assert (await client.get(f'/textbooks/chapters/{identifier}')).status_code == 404
        async with sessions() as db:
            with pytest.raises(HTTPException) as error:
                await confirmed_chapter(db, identifier, '化学', '初中')
            assert error.value.status_code == 422
            assert await db.get(TextbookChapter, identifier) is not None
    for title in EXCLUDED:
        response = await client.post(f'/textbooks/{book_id}/chapters', headers=ADMIN,
                                    json=dict(title=title, start_page=1, end_page=1,
                                              content=CHAPTER_TEXT, is_published=True))
        assert response.status_code == 422
        assert '化学' in response.json()['detail']
