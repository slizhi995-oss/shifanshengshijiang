"""Grade 7–8 English table labels, nested sections and real source page bindings."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_junior_english import (
    junior_english_directory, junior_english_topic_chapters,
    expand_junior_english_chapters, reviewed_junior_english_directories,
)
from app.services.textbook_units import group_chapter_directory
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_english_sections import section_chapters_from_review
from test_textbook_pipeline import environment, CHAPTER_TEXT


DIGEST = 'd888b6264c021f87592c6f31cb657bf5ecd8963880df3aa4760fa0958b20fd52'
NINTH_GRADE = 'eed40cb54f3c5a2680a5ca039bdca05410eb87a662eedb57dd25f18d02c37712'
UNIT = 'UNIT 3 My School (What do you like about your school?)'
A = 'Section A: What is your school like?'
B = 'Section B: What fun things do you do at school?'


def source_pages():
    return [f'Unique source page {number}. '+CHAPTER_TEXT for number in range(1, 155)]


def rows_for(digest=DIGEST):
    return [dict(id=index, book_id=1, **row) for index, row in enumerate(
        junior_english_topic_chapters(digest, source_pages()), 1)]


def sections_for(digest=DIGEST):
    return [dict(id=index, book_id=1, **row) for index, row in enumerate(
        section_chapters_from_review(reviewed_junior_english_directories()[digest], source_pages(), junior=True), 1)]


def test_uploaded_example_has_exact_hierarchy_labels_and_order():
    rows = sections_for()
    before = deepcopy(rows)
    directory = group_chapter_directory(SimpleNamespace(subject='英语', grade='初中七年级', sha256=DIGEST), list(reversed(rows)))
    school = [row for row in directory if row['unit_title'] == UNIT]
    assert [(row['section_title'], row['title']) for row in school] == [('', A), ('', B)]
    assert all(row['directory_layout'] == 'sections' for row in directory)
    assert all(not row['is_unit'] and not row['is_nested'] for row in directory)
    assert rows == before


def test_grammar_display_position_does_not_change_its_actual_body_page():
    rows = rows_for()
    grammar = next(row for row in rows if row['parent_title'] == UNIT+' · '+B and row['title'].startswith('Grammar:'))
    assert (grammar['start_page'], grammar['end_page'], grammar['printed_pages']) == (48, 48, '39')
    assert 'Unique source page 48.' in grammar['content']
    assert 'Unique source page 49.' not in grammar['content']
    reading = next(row for row in rows if row['parent_title'] == UNIT+' · '+B and row['title'].startswith('Reading:'))
    assert (reading['start_page'], reading['end_page']) == (49, 50)
    project = next(row for row in rows if row['parent_title'] == UNIT+' · *Project')
    assert (project['start_page'], project['end_page']) == (51, 51)


def test_all_five_books_have_complete_labels_and_valid_idempotent_source_bindings():
    reviews = reviewed_junior_english_directories()
    assert len(reviews) == 5
    assert sum(len(review['units']) for review in reviews.values()) == 42
    assert NINTH_GRADE not in reviews
    count = 0
    for digest, review in reviews.items():
        rows = junior_english_topic_chapters(digest, source_pages())
        count += len(rows)
        assert all(row['is_published'] for row in rows)
        assert all(max(len(row['title']), len(row['parent_title'])) <= 160 for row in rows)
        assert len({(row['parent_title'], row['title']) for row in rows}) == len(rows)
        merged = expand_junior_english_chapters(digest, rows, source_pages())
        assert len(merged) == 2 * len(review['units'])
        assert expand_junior_english_chapters(digest, merged, source_pages()) == merged
        for unit in review['units']:
            assert [section['title'].split(':')[0] for section in unit['sections']] == ['Section A', 'Section B', '*Project']
            assert all(section['items'] for section in unit['sections'])
    assert count == 296
    with pytest.raises(ValueError, match='outside source PDF'):
        junior_english_topic_chapters(DIGEST, [CHAPTER_TEXT])


def test_starter_units_keep_combined_tasks_and_actual_key_sentences():
    rows = rows_for()
    starter = [row for row in rows if row['parent_title'].startswith('STARTER UNIT 1 Hello! · ')]
    assert len(starter) == 5
    assert starter[0]['title'] == 'Listening and Speaking: Greet each other'
    assert (starter[0]['start_page'], starter[0]['end_page']) == (10, 11)
    assert starter[2]['title'] == 'Reading and Writing: Start a conversation'
    assert starter[3]['title'].startswith('Key Sentences: Hi. / Hello.')
    assert starter[-1]['title'] == 'Learn how to use a dictionary'
    assert starter[-1]['start_page'] == 15


def test_eighth_grade_follows_its_actual_columns_and_preserves_wrapped_words():
    reviews = reviewed_junior_english_directories()
    upper = next(digest for digest, review in reviews.items() if review['title'] == '八年级上册')
    lower = next(digest for digest, review in reviews.items() if review['title'] == '八年级下册')
    upper_rows = rows_for(upper)
    grammar = next(row for row in upper_rows if row['title'].startswith('Grammar:'))
    vocabulary = next(row for row in upper_rows if row['title'].startswith('Vocabulary:'))
    assert ' · Section A:' in grammar['parent_title']
    assert ' · Section B:' in vocabulary['parent_title']
    assert vocabulary['start_page'] == 17
    lower_rows = rows_for(lower)
    assert all(not row['title'].startswith('Pronunciation:') for row in lower_rows)
    assert next(row for row in lower_rows if row['title'].startswith('Listening:'))['title'] == (
        'Listening: A survey on free-time activities & A conversation about taking up a hobby')
    assert any(row['title'] == 'Reading: An article about Chinese achievements on Mount Qomolangma' for row in lower_rows)


def test_historical_unit_ids_are_preserved_and_supplements_are_removed():
    rows = sections_for()+[
        dict(id=1000, title='Starter Unit 1 Hello!', parent_title='', start_page=10),
        dict(id=1001, title='Unit 3 My School', parent_title='', start_page=44),
        dict(id=1002, title='Grammar', parent_title='', start_page=104)]
    before = deepcopy(rows)
    directory = group_chapter_directory(SimpleNamespace(subject='英语', grade='初中七年级', sha256=DIGEST), rows)
    result = {row['id']: row for row in directory}
    assert result[1000]['is_unit'] and result[1000]['unit_title'] == 'STARTER UNIT 1 Hello!'
    assert result[1001]['is_unit'] and result[1001]['display_title'] == UNIT
    assert result[1001]['title'] == 'Unit 3 My School'
    assert 1002 not in result
    assert all(row['unit_title'] for row in directory)
    assert rows == before


@pytest.mark.parametrize('title', ['*Reading Plus', 'Listening Scripts', 'Pronunciation', 'Grammar',
    'Vocabulary in Each Unit', 'Vocabulary A–Z', 'Vocabulary from Primary School',
    'Reference Word List', 'Irregular Verbs', '其他章节'])
def test_remove_supplements_without_removing_in_unit_tasks_or_ninth_grade(title):
    assert is_removed_chapter('英语', title, '初中七年级')
    assert is_removed_chapter('英语', title, '初中八年级')
    assert not is_removed_chapter('英语', title, '初中九年级')
    assert not is_removed_chapter('语文', title, '初中七年级')
    assert not is_removed_chapter('英语', 'Grammar: There be structure & Prepositions of position', '初中七年级')
    assert not is_removed_chapter('英语', 'Pronunciation: /ɔː/, /ɒ/ & Word stress (2)', '初中七年级')


def test_ninth_grade_and_other_editions_are_outside_this_change():
    original = [dict(title='Unit 1 How can we become good learners?', parent_title='', start_page=16)]
    for digest in (NINTH_GRADE, 'unknown-edition'):
        assert junior_english_topic_chapters(digest, source_pages()) == []
        assert expand_junior_english_chapters(digest, original, source_pages()) == original
        assert junior_english_directory(SimpleNamespace(sha256=digest), original) is None


@pytest.mark.asyncio
async def test_student_api_exposes_source_questions_and_selected_topic_content(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='七年级上册', subject='英语', grade='初中七年级', sha256=DIGEST,
            original_filename='初中英语七年级上册.pdf', file_path='missing-junior-english.pdf',
            page_count=138, is_published=True)
        db.add(book)
        await db.flush()
        for row in sections_for():
            db.add(TextbookChapter(book_id=book.id, **{key: value for key, value in row.items() if key not in ('id', 'book_id')}))
        hidden = TextbookChapter(book_id=book.id, title='Unpublished task', parent_title=UNIT+' · '+A,
            start_page=45, end_page=47, printed_pages='36-38', content=CHAPTER_TEXT, is_published=False)
        db.add(hidden)
        supplement = TextbookChapter(book_id=book.id, title='*Reading Plus', parent_title='',
            start_page=84, end_page=90, printed_pages='75-81', content=CHAPTER_TEXT, is_published=True)
        db.add(supplement)
        await db.commit()
        identifier, hidden_id = book.id, hidden.id
        supplement_id = supplement.id
    response = await client.get(f'/textbooks/{identifier}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert all(row['id'] != hidden_id for row in rows)
    assert all(row['id'] != supplement_id for row in rows)
    assert all(row['unit_title'] for row in rows)
    grammar = next(row for row in rows if row['unit_title'] == UNIT and row['title'] == B)
    assert grammar['section_title'] == '' and not grammar['is_unit']
    detail = await client.get(f'/textbooks/chapters/{grammar["id"]}')
    assert detail.status_code == 200
    assert detail.json()['data']['start_page'] == 48
    assert 'Unique source page 48.' in detail.json()['data']['content']
    assert (await client.get(f'/textbooks/chapters/{hidden_id}')).status_code == 404
    assert (await client.get(f'/textbooks/chapters/{supplement_id}')).status_code == 404
    recommendations = (await client.get('/textbooks/recommend', params=dict(
        subject='英语', grade='初中七年级', topic='Reading Plus'))).json()['data']
    assert all(row['id'] != supplement_id for row in recommendations)
