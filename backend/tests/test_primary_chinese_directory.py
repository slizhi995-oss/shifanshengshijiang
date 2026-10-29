"""Primary-Chinese supplementary tables are excluded without losing lessons."""
import json

import pytest
from fastapi import HTTPException

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_service import confirmed_chapter
from test_textbook_pipeline import environment, CHAPTER_TEXT, ADMIN


TABLES = ['识字表', '写字表', '笔画名称表', '常用偏旁名称表', '词语表']


@pytest.mark.parametrize('title', TABLES+['其他章节', '◎ 识字表', '12. 写字表', '常用偏旁 名称表', '词语表……'])
def test_supplement_removal_is_limited_to_primary_chinese(title):
    for year in '一二三四五六':
        assert is_removed_chapter('语文', title, f'小学{year}年级')
    assert not is_removed_chapter('语文', title, '初中七年级')
    assert not is_removed_chapter('语文', title, '高中一年级')
    assert not is_removed_chapter('英语', title, '小学一年级')


@pytest.mark.parametrize('title', ['我是中国人', '我爱我们的祖国', '我是小学生', '我爱学语文',
    '第一单元·识字', '1 天地人', '1 神州谣', '16 表里的生物', '◎ 口语交际:怎么表演课本剧',
    '◎ 语文园地一', '古诗词诵读', '快乐读书吧'])
def test_teaching_content_remains_available(title):
    assert not is_removed_chapter('语文', title, '小学一年级')


def test_old_import_cache_cannot_reintroduce_word_tables(tmp_path):
    from scripts.import_textbook_library import parse, PARSER_VERSION
    sha = 'primary-chinese-cache-fixture'
    source = tmp_path/'小学语文一年级上册.pdf'
    cache = tmp_path/'cache'/f'{sha}-v{PARSER_VERSION}.json'
    cache.parent.mkdir()
    titles = ['我是中国人', '1 天地人', '◎ 语文园地一']+TABLES
    cache.write_text(json.dumps(dict(pages=[CHAPTER_TEXT], chapters=[
        dict(title=title) for title in titles]), ensure_ascii=False), encoding='utf8')
    assert [row['title'] for row in parse(source, sha, tmp_path)['chapters']] == titles[:3]


@pytest.mark.asyncio
async def test_student_directory_retrieval_and_generation_exclude_tables(environment):
    client, sessions, _ = environment
    teaching = ['我是中国人', '我爱我们的祖国', '我是小学生', '我爱学语文',
        '第一单元', '1 天地人', '◎ 语文园地一']
    async with sessions() as db:
        book = Textbook(title='一年级上册', subject='语文', grade='小学一年级', volume='一年级上册',
            sha256='primary-chinese-fixture', original_filename='小学语文一年级上册.pdf',
            file_path='missing-test-source.pdf', page_count=20, is_published=True)
        db.add(book)
        await db.flush()
        chapters = [TextbookChapter(book_id=book.id, title=title, parent_title='',
            start_page=index+1, end_page=index+1, content=CHAPTER_TEXT, is_published=True)
            for index, title in enumerate(teaching+TABLES)]
        db.add_all(chapters)
        await db.commit()
        book_id = book.id
        teaching_id = chapters[5].id
        removed_ids = [row.id for row in chapters[len(teaching):]]
    response = await client.get(f'/textbooks/{book_id}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert [row['title'] for row in rows] == teaching
    assert all(row['unit_title'] == '' for row in rows[:4])
    assert next(row for row in rows if row['id'] == teaching_id)['unit_title'] == '第一单元'
    response = await client.get('/textbooks/recommend', params=dict(subject='语文', grade='小学一年级', book_id=book_id))
    assert not set(removed_ids).intersection(row['id'] for row in response.json()['data'])
    assert (await client.get(f'/textbooks/chapters/{teaching_id}')).status_code == 200
    async with sessions() as db:
        chapter, book = await confirmed_chapter(db, teaching_id, '语文', '小学一年级')
        assert chapter.title == '1 天地人' and book.id == book_id
    for chapter_id in removed_ids:
        assert (await client.get(f'/textbooks/chapters/{chapter_id}')).status_code == 404
        async with sessions() as db:
            with pytest.raises(HTTPException) as error:
                await confirmed_chapter(db, chapter_id, '语文', '小学一年级')
            assert error.value.status_code == 422
    response = await client.post(f'/textbooks/{book_id}/chapters', headers=ADMIN,
        json=dict(title='识字表', start_page=15, end_page=15, content=CHAPTER_TEXT, is_published=True))
    assert response.status_code == 422 and '小学语文' in response.json()['detail']
