"""English table columns become topics while preserving their real source pages."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_english import (
    english_topic_chapters, expand_english_chapters, reviewed_english_directories,
)
from app.services.textbook_units import group_chapter_directory
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_english_sections import section_chapters_from_review
from test_textbook_pipeline import environment, CHAPTER_TEXT


DIGEST = 'fe798cdc7010b208a1fa952f3eb4c60d853e50e745908b27e7dc89ad01b7d906'


def topic_rows():
    return [dict(id=index, book_id=1, **row) for index, row in enumerate(
        english_topic_chapters(DIGEST, [f'Unique source page {n}. '+CHAPTER_TEXT for n in range(1, 134)]), 1)]


def section_rows():
    return [dict(id=index, book_id=1, **row) for index, row in enumerate(
        section_chapters_from_review(reviewed_english_directories()[DIGEST],
            [f'Unique source page {n}. '+CHAPTER_TEXT for n in range(1, 134)]), 1)]


def test_example_has_exact_column_order_and_no_strategy_or_empty_cell():
    rows = section_rows()
    original = deepcopy(rows)
    directory = group_chapter_directory(SimpleNamespace(subject='英语', grade='高中一年级', sha256=DIGEST),
                                        list(reversed(rows)))
    unit = [row for row in directory if row['unit_title'] == 'UNIT 1 TEENAGE LIFE']
    assert [row['title'] for row in unit] == [
        'Listening', 'Speaking', 'Reading', 'Writing', 'Pronunciation', 'Structure', 'Project', '*Video Time']
    assert all(row['section_title'] == '' and row['directory_layout'] == 'sections' for row in unit)
    assert rows == original
    assert all(not row['is_unit'] and not row['is_nested'] for row in directory)
    welcome = [row for row in directory if row['unit_title'] == 'WELCOME UNIT']
    assert not any(row['title'] in ('Project', '*Video Time') for row in welcome)


def test_workbook_reading_keeps_its_own_page_instead_of_main_unit_range():
    row = next(row for row in topic_rows() if row['title'] == 'The Face-down Generation')
    assert (row['start_page'], row['end_page'], row['printed_pages']) == (79, 79, '74')
    assert '[PDF第79页]' in row['content'] and 'Unique source page 79.' in row['content']
    assert 'Unique source page 19.' not in row['content']
    reading = next(row for row in topic_rows() if row['title'] == 'The Freshman Challenge')
    assert (reading['start_page'], reading['end_page']) == (19, 20)


def test_all_seven_books_have_complete_units_and_valid_bindings():
    reviews = reviewed_english_directories()
    assert len(reviews) == 7
    assert sum(len(review['units']) for review in reviews.values()) == 36
    count = 0
    for digest, review in reviews.items():
        rows = english_topic_chapters(digest, [CHAPTER_TEXT]*150)
        count += len(rows)
        assert all(row['is_published'] for row in rows)
        assert len({(row['parent_title'], row['title']) for row in rows}) == len(rows)
        assert all(1 <= row['start_page'] <= row['end_page'] <= 150 for row in rows)
        merged = expand_english_chapters(digest, rows, [CHAPTER_TEXT]*150)
        assert len(merged) == sum(len(unit['sections']) for unit in review['units'])
        assert expand_english_chapters(digest, merged, [CHAPTER_TEXT]*150) == merged
        titles = {row['title'].lower() for row in rows}
        assert not titles & {'skim', 'scan', 'predict content', 'find descriptive words', 'recognise examples'}
    assert count == 387
    assert english_topic_chapters('unreviewed-digest', [CHAPTER_TEXT]*150) == []
    with pytest.raises(ValueError, match='outside source PDF'):
        english_topic_chapters(DIGEST, [CHAPTER_TEXT])


@pytest.mark.parametrize('volume,topic,pages', [
    ('选择性必修一', 'Theme Parks—Fun and More Than Fun', (37, 39)),
    ('选择性必修一', 'Chemical Versus Organic Farming', (61, 63)),
    ('选择性必修二', "The Father of China's Aerospace; A World of Pure Thought", (11, 13)),
    ('选择性必修四', 'Summer Camp Helpers Wanted', (61, 63)),
])
def test_reading_starting_on_shared_listening_page_includes_opening_paragraph(volume, topic, pages):
    digest = next(digest for digest, review in reviewed_english_directories().items() if review['title'] == volume)
    row = next(row for row in english_topic_chapters(digest, [CHAPTER_TEXT]*150) if row['title'] == topic)
    assert (row['start_page'], row['end_page']) == pages
    assert f'[PDF第{pages[0]}页]' in row['content']


def test_unit_heading_and_supplements_preserve_historical_records():
    rows = [dict(id=1000, title='Welcome Unit', start_page=6, parent_title=''),
            dict(id=1001, title='Unit 1 Teenage Life', start_page=16, parent_title=''),
            dict(id=1002, title='Workbook Unit 1', start_page=76, parent_title=''),
            dict(id=1003, title='Notes', start_page=106, parent_title='')]+section_rows()
    before = deepcopy(rows)
    directory = group_chapter_directory(SimpleNamespace(subject='英语', grade='高中', sha256=DIGEST), rows)
    assert rows == before
    by_id = {row['id']: row for row in directory}
    assert by_id[1000]['is_unit'] and by_id[1000]['unit_title'] == 'WELCOME UNIT'
    assert by_id[1001]['is_unit'] and by_id[1001]['unit_title'] == 'UNIT 1 TEENAGE LIFE'
    assert not by_id[1002]['is_unit'] and by_id[1002]['unit_title'] == 'WORKBOOK'
    assert by_id[1002]['display_title'] == 'Unit 1'
    assert by_id[1002]['title'] == 'Workbook Unit 1' and by_id[1002]['start_page'] == 76
    assert 1003 not in by_id


@pytest.mark.parametrize('title', ['Notes', 'Grammar', 'Words and Expressions in Each Unit',
    'Vocabulary', 'Irregular Verbs', 'APPENDICES', 'Appendix I', '１２．Notes'])
def test_appendices_removed_only_from_highschool_english(title):
    assert is_removed_chapter('英语', title, '高中')
    assert is_removed_chapter('英语', title, '高中一年级')
    assert not is_removed_chapter('英语', title, '初中')
    assert not is_removed_chapter('语文', title, '高中')
    assert not is_removed_chapter('英语', 'Workbook Unit 1', '高中')
    assert not is_removed_chapter('英语', 'Basic sentence structures', '高中')


def test_workbook_units_are_ordered_and_selectable_in_all_seven_books():
    rows = [dict(id=number, title=f'Workbook Unit {number}', start_page=70+number,
                 end_page=75+number, parent_title='', content=CHAPTER_TEXT) for number in (5, 2, 4, 1, 3)]
    before = deepcopy(rows)
    for digest in reviewed_english_directories():
        directory = group_chapter_directory(SimpleNamespace(subject='英语', grade='高中', sha256=digest), rows)
        assert [row['display_title'] for row in directory] == [f'Unit {number}' for number in range(1, 6)]
        assert all(row['unit_title'] == 'WORKBOOK' and row['section_title'] == '' and not row['is_unit'] for row in directory)
    assert rows == before


@pytest.mark.asyncio
async def test_student_api_exposes_column_topics_and_retrieves_original_content(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='必修一', subject='英语', grade='高中', sha256=DIGEST,
                        original_filename='高中英语必修一.pdf', file_path='missing-english.pdf',
                        page_count=133, is_published=True)
        db.add(book)
        await db.flush()
        for row in section_rows():
            db.add(TextbookChapter(book_id=book.id, **{key: value for key, value in row.items() if key not in ('id', 'book_id')}))
        hidden = TextbookChapter(book_id=book.id, title='Unpublished topic', parent_title='UNIT 1 TEENAGE LIFE · Reading',
                                 start_page=19, end_page=20, printed_pages='14-15', content=CHAPTER_TEXT, is_published=False)
        db.add(hidden)
        appendix = TextbookChapter(book_id=book.id, title='Notes', parent_title='',
            start_page=106, end_page=112, printed_pages='101-107', content=CHAPTER_TEXT, is_published=True)
        workbook = TextbookChapter(book_id=book.id, title='Workbook Unit 1', parent_title='',
            start_page=76, end_page=81, printed_pages='71-76', content=CHAPTER_TEXT, is_published=True)
        db.add_all([appendix, workbook])
        await db.commit()
        identifier = book.id
        hidden_id = hidden.id
        appendix_id = appendix.id
        workbook_id = workbook.id
    response = await client.get(f'/textbooks/{identifier}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert all(row['id'] != hidden_id for row in rows)
    assert all(row['id'] != appendix_id for row in rows)
    workbook_row = next(row for row in rows if row['id'] == workbook_id)
    assert workbook_row['display_title'] == 'Unit 1' and workbook_row['unit_title'] == 'WORKBOOK'
    assert not workbook_row['is_unit']
    reading = next(row for row in rows if row['title'] == 'Reading' and row['unit_title'] == 'UNIT 1 TEENAGE LIFE')
    assert reading['section_title'] == '' and reading['directory_layout'] == 'sections'
    detail = await client.get(f'/textbooks/chapters/{reading["id"]}')
    assert detail.status_code == 200
    assert detail.json()['data']['start_page'] == 19
    assert detail.json()['data']['printed_pages'] == '14-15, 18-19, 74'
    assert 'Unique source page 79.' in detail.json()['data']['content']
    assert 'Unique source page 78.' not in detail.json()['data']['content']
    assert (await client.get(f'/textbooks/chapters/{hidden_id}')).status_code == 404
    assert (await client.get(f'/textbooks/chapters/{appendix_id}')).status_code == 404
    assert (await client.get(f'/textbooks/chapters/{workbook_id}')).status_code == 200
    recommendations = (await client.get('/textbooks/recommend', params=dict(subject='英语', grade='高中', topic='Notes'))).json()['data']
    assert all(row['id'] != appendix_id for row in recommendations)
