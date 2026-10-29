"""Primary English exposes the printed lesson/time columns as selectable rows."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_primary_english import (
    reviewed_primary_english_directories, primary_english_topic_chapters,
    primary_english_directory, expand_primary_english_chapters,
)
from app.services.textbook_units import group_chapter_directory
from app.services.textbook_catalog import is_removed_chapter
from test_textbook_pipeline import environment, CHAPTER_TEXT


DIGEST = '6b7173b16c8029dc6aa333fa119557b1f44f414e4d01afdbff4e5772321e74c7'
UNIT = 'Unit 1 Greetings'
LABELS = ['Lesson 1', 'Lesson 2', 'Lesson 3', 'Fun Time', 'Story Time']


def source_pages():
    return [f'Unique source page {number}. '+CHAPTER_TEXT for number in range(1, 107)]


def topic_rows(digest=DIGEST):
    return [dict(id=index, book_id=1, **row) for index, row in enumerate(
        primary_english_topic_chapters(digest, source_pages()), 1)]


def test_uploaded_example_is_unit_with_five_flat_indented_options():
    rows = topic_rows()
    before = deepcopy(rows)
    directory = group_chapter_directory(SimpleNamespace(subject='英语', grade='小学三年级', sha256=DIGEST), list(reversed(rows)))
    unit = [row for row in directory if row['unit_title'] == UNIT]
    assert [row['display_title'] for row in unit] == LABELS
    assert all(row['section_title'] == '' and not row['is_unit'] and not row['is_nested'] for row in unit)
    assert rows == before
    # Internal titles keep the unit context for topic autofill and generation.
    assert unit[0]['title'] == 'Unit 1 Greetings · Lesson 1'
    assert [row['display_title'] for row in directory if row['unit_title'] == 'Unit 4 Friends'] == LABELS


def test_lessons_and_time_sections_retrieve_their_own_two_pages():
    rows = [row for row in topic_rows() if row['parent_title'] == UNIT]
    assert [(row['start_page'], row['end_page'], row['printed_pages']) for row in rows] == [
        (11, 12, '4-5'), (13, 14, '6-7'), (15, 16, '8-9'), (17, 18, '10-11'), (19, 20, '12-13')]
    for row in rows:
        assert f'Unique source page {row["start_page"]}.' in row['content']
        assert f'Unique source page {row["end_page"]}.' in row['content']
        assert 'Unique source page 9.' not in row['content']
        assert 'Unique source page 21.' not in row['content']


def test_all_three_editions_have_six_units_and_ninety_topics():
    reviews = reviewed_primary_english_directories()
    assert {review['title'] for review in reviews.values()} == {'三年级上册', '三年级下册', '四年级上册'}
    count = 0
    for digest, review in reviews.items():
        assert len(review['units']) == 6
        rows = primary_english_topic_chapters(digest, source_pages())
        assert len(rows) == 30
        count += len(rows)
        assert len({(row['parent_title'], row['title']) for row in rows}) == 30
        assert all(row['is_published'] and row['end_page']-row['start_page'] == 1 for row in rows)
        assert expand_primary_english_chapters(digest, rows, source_pages()) == rows
        for unit in review['units']:
            assert [item['title'] for item in unit['items']] == LABELS
    assert count == 90
    with pytest.raises(ValueError, match='outside source PDF'):
        primary_english_topic_chapters(DIGEST, [CHAPTER_TEXT])


def test_preserve_unit_ids_and_remove_all_supplements():
    rows = topic_rows()+[
        dict(id=1000, title=UNIT, parent_title='', start_page=9),
        dict(id=1001, title='Revision 1', parent_title='', start_page=45),
        dict(id=1002, title='Appendix 3 Vocabulary A-Z', parent_title='', start_page=98)]
    before = deepcopy(rows)
    directory = group_chapter_directory(SimpleNamespace(subject='英语', grade='小学三年级', sha256=DIGEST), rows)
    by_id = {row['id']: row for row in directory}
    assert by_id[1000]['is_unit'] and by_id[1000]['unit_title'] == UNIT
    assert 1001 not in by_id and 1002 not in by_id
    assert len(directory) == 31
    assert expand_primary_english_chapters(DIGEST, rows, source_pages()) == rows[:-2]
    assert rows == before


@pytest.mark.parametrize('title', ['Revision 1', 'Revision 2', 'Appendix 3 Vocabulary A-Z',
    'Appendix 4 The English alphabet', '其他章节', 'Other supplementary content'])
def test_supplement_removal_is_bound_to_the_three_reviewed_pdfs(title):
    for digest in reviewed_primary_english_directories():
        assert is_removed_chapter('英语', title, '小学三年级', digest)
        assert not is_removed_chapter('数学', title, '小学三年级', digest)
    assert not is_removed_chapter('英语', UNIT, '小学三年级', DIGEST)
    assert not is_removed_chapter('英语', UNIT+' · Story Time', '小学三年级', DIGEST)
    assert not is_removed_chapter('英语', 'Revision 1', '初中七年级', DIGEST)
    assert not is_removed_chapter('英语', title, '小学四年级', 'different-fourth-grade-volume')
    assert not is_removed_chapter('英语', title, '小学三年级')


@pytest.mark.parametrize('digest', [
    'unknown-edition', 'unreviewed-custom-primary-edition'])
def test_other_primary_editions_are_unchanged(digest):
    original = [dict(title='Unit 1 Original title', parent_title='', start_page=8)]
    assert primary_english_topic_chapters(digest, source_pages()) == []
    assert expand_primary_english_chapters(digest, original, source_pages()) == original
    assert primary_english_directory(SimpleNamespace(sha256=digest), original) is None


@pytest.mark.asyncio
async def test_student_api_returns_short_labels_and_keeps_selected_unit_context(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='三年级上册', subject='英语', grade='小学三年级', sha256=DIGEST,
            original_filename='小学英语三年级上册.pdf', file_path='missing-primary-english.pdf', page_count=106, is_published=True)
        db.add(book)
        await db.flush()
        for row in topic_rows():
            db.add(TextbookChapter(book_id=book.id, **{key: value for key, value in row.items() if key not in ('id', 'book_id')}))
        hidden = TextbookChapter(book_id=book.id, title=UNIT+' · Unpublished lesson', parent_title=UNIT,
            start_page=11, end_page=12, printed_pages='4-5', content=CHAPTER_TEXT, is_published=False)
        db.add(hidden)
        supplements = [TextbookChapter(book_id=book.id, title=title, parent_title='',
            start_page=45, end_page=46, content=CHAPTER_TEXT, is_published=True)
            for title in ('Revision 1', 'Appendix 3 Vocabulary A-Z')]
        db.add_all(supplements)
        await db.commit()
        identifier, hidden_id = book.id, hidden.id
        supplement_ids = [row.id for row in supplements]
    response = await client.get(f'/textbooks/{identifier}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert all(row['id'] != hidden_id for row in rows)
    assert not set(supplement_ids).intersection(row['id'] for row in rows)
    unit = [row for row in rows if row['unit_title'] == UNIT]
    assert [row['display_title'] for row in unit] == LABELS
    response = await client.get(f'/textbooks/chapters/{unit[0]["id"]}')
    assert response.status_code == 200
    detail = response.json()['data']
    assert detail['title'] == UNIT+' · Lesson 1'
    assert detail['parent_title'] == UNIT and detail['start_page'] == 11
    assert 'Unique source page 11.' in detail['content']
    assert (await client.get(f'/textbooks/chapters/{hidden_id}')).status_code == 404
    response = await client.get('/textbooks/recommend', params=dict(subject='英语', grade='小学三年级', book_id=identifier))
    assert response.status_code == 200
    assert not set(supplement_ids).intersection(row['id'] for row in response.json()['data'])
    from fastapi import HTTPException
    from app.services.textbook_service import confirmed_chapter
    for supplement_id in supplement_ids:
        assert (await client.get(f'/textbooks/chapters/{supplement_id}')).status_code == 404
        async with sessions() as db:
            with pytest.raises(HTTPException) as error:
                await confirmed_chapter(db, supplement_id, '英语', '小学三年级')
            assert error.value.status_code == 422
