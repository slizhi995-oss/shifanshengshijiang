"""History appendix entries are excluded without removing ungrouped lessons."""
import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import is_removed_chapter
from test_textbook_pipeline import environment, CHAPTER_TEXT


@pytest.mark.parametrize('grade', ['初中七年级', '高中'])
@pytest.mark.parametrize('title', ['附录', '附录 中国古代史大事年表', '１２．附 录Ⅰ 年表', '其他章节', '译名对照表(下)', '历史译名对照表（下）'])
def test_history_supplements_are_excluded(grade, title):
    assert is_removed_chapter('历史', title, grade)
    assert not is_removed_chapter('历史', '第1课 古代文明', grade)
    assert not is_removed_chapter('历史', '活动课 历史探究', grade)
    assert not is_removed_chapter('语文', title, grade)


@pytest.mark.asyncio
@pytest.mark.parametrize('grade', ['初中七年级', '高中'])
async def test_history_api_keeps_lessons_and_excludes_supplements(environment, grade):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='历史', subject='历史', grade=grade, sha256='history-directory-test',
                        original_filename='历史.pdf', file_path='missing-history.pdf',
                        page_count=20, is_published=True)
        db.add(book)
        await db.flush()
        rows = [TextbookChapter(book_id=book.id, title=title, parent_title='', start_page=i,
                               end_page=i, content=CHAPTER_TEXT, is_published=True)
                for i, title in enumerate(['第1课 古代文明', '活动课 历史探究', '附录 年表', '其他章节', '译名对照表(下)'], 1)]
        db.add_all(rows)
        await db.commit()
        book_id = book.id
        removed_ids = [row.id for row in rows[2:]]
    response = await client.get(f'/textbooks/{book_id}/chapters')
    assert response.status_code == 200
    assert [row['title'] for row in response.json()['data']] == ['第1课 古代文明', '活动课 历史探究']
    for identifier in removed_ids:
        assert (await client.get(f'/textbooks/chapters/{identifier}')).status_code == 404
