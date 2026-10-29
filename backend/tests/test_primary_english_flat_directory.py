"""Older primary-English books expose complete units and Fun Time as peers."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import filename_metadata, is_removed_chapter
from app.services.textbook_outline import reviewed_directory
from app.services.textbook_primary_english import (
    FLAT_PRIMARY_ENGLISH_DIGESTS, reviewed_flat_primary_english_directory, expand_primary_english_chapters,
)
from app.services.textbook_service import confirmed_chapter
from app.services.textbook_units import group_chapter_directory
from test_textbook_pipeline import environment, CHAPTER_TEXT


FOUR_DOWN = '20d8721c3e613f007a1a2b6c7c5cb5ca5786e4a5b14e0bb0197c8017bf148499'


def source_rows(digest):
    review = reviewed_directory(digest)
    return [dict(id=index+1, book_id=1, title=entry['title'], parent_title='',
        start_page=entry['printed']+review['offset'], end_page=entry['printed']+review['offset'],
        printed_pages=str(entry['printed']), content=entry['title']+' '+CHAPTER_TEXT, is_published=True)
        for index, entry in enumerate(review['entries'])]


@pytest.mark.parametrize('digest', sorted(FLAT_PRIMARY_ENGLISH_DIGESTS))
def test_units_and_fun_time_are_flat_selectable_source_ordered_entries(digest):
    review = reviewed_flat_primary_english_directory(digest)
    metadata = filename_metadata(review['filename'])
    book = SimpleNamespace(sha256=digest, **metadata)
    rows = source_rows(digest)
    before = deepcopy(rows)
    directory = group_chapter_directory(book, list(reversed(rows)))
    assert [row['title'] for row in directory] == [entry['title'] for entry in review['entries']]
    assert all(row['directory_layout'] == 'flat' and not row['is_unit'] and not row['is_nested']
        and row['unit_title'] == '' and row['section_title'] == '' for row in directory)
    refreshed = digest in {
        'b47ee47d590565e4d5644cdca3f5f7bebae09289833b54dcd865fb4bcf361c44',
        '300cc235eef8705807355496ae9f8b95a3718d4e947e9d2ffc9d52d45e8235db',
        'e2a5fdda9147dc91e0b7afc5bf451459d6eb84d96d858629efd31ba7bb583763',
        '125831084793f9df01f90b2fb7bcf2f0850b209daa74abbf74661e16b0c0ce27',
    }
    if refreshed:
        assert len(directory) == (4 if metadata['title'] == '六年级下册' else 6)
        assert all(row['title'].startswith('Unit ') for row in directory)
    elif metadata['title'] == '六年级下册':
        assert len(directory) == 7
        assert directory[3]['title'] == 'Fun Time'
        assert [row['title'] for row in directory[-3:]] == [f'Unit {n+3} General Revision {n}' for n in (1, 2, 3)]
    else:
        assert len(directory) == 8 and directory[-1]['title'] == 'Fun Time 2'
        assert directory[3]['title'].startswith('Fun Time')
    allowed = {entry['title'] for entry in review['entries']}
    for row in rows:
        assert is_removed_chapter('英语', row['title'], metadata['grade'], digest) == (row['title'] not in allowed)
    assert expand_primary_english_chapters(digest, rows, []) == [row for row in rows if row['title'] in allowed]
    assert rows == before


@pytest.mark.asyncio
async def test_fourth_grade_example_api_and_generation_exclude_supplements(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(**filename_metadata('小学英语四年级下册.pdf'), sha256=FOUR_DOWN,
            original_filename='小学英语四年级下册.pdf', file_path='missing-test-source.pdf', page_count=98, is_published=True)
        db.add(book)
        await db.flush()
        for row in source_rows(FOUR_DOWN):
            db.add(TextbookChapter(book_id=book.id, **{key: value for key, value in row.items() if key not in ('id', 'book_id')}))
        await db.commit()
        identifier = book.id
    response = await client.get(f'/textbooks/{identifier}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert [row['title'] for row in rows] == [
        'Unit 1 Welcome to my new home!', 'Unit 2 There are forty students in our class',
        'Unit 3 What subject do you like best?', 'Fun Time 1', 'Unit 4 There are seven days in a week.',
        'Unit 5 What will you do this weekend?', 'Unit 6 Would you like to take a trip?', 'Fun Time 2']
    assert all(row['is_unit'] is False and row['directory_layout'] == 'flat' for row in rows)
    response = await client.get('/textbooks/recommend', params=dict(subject='英语', grade='小学四年级', book_id=identifier))
    assert {row['id'] for row in response.json()['data']} == {row['id'] for row in rows}
    async with sessions() as db:
        chapter, selected_book = await confirmed_chapter(db, rows[0]['id'], '英语', '小学四年级')
        assert selected_book.id == identifier and chapter.start_page == 9 and CHAPTER_TEXT in chapter.content
    for removed in (9, 10):
        assert (await client.get(f'/textbooks/chapters/{removed}')).status_code == 404
        async with sessions() as db:
            with pytest.raises(HTTPException) as error:
                await confirmed_chapter(db, removed, '英语', '小学四年级')
            assert error.value.status_code == 422
