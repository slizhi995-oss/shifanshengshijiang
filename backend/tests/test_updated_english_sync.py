"""Replacement editions: source ranges, idempotency and historical references."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.textbook import Textbook, TextbookChapter, TextbookLesson, TextbookPage
from app.services.textbook_catalog import filename_metadata, is_removed_chapter
from app.services.textbook_junior_english import junior_english_topic_chapters
from app.services.textbook_junior_english import reviewed_junior_english_directories
from app.services.textbook_english_sections import section_chapters_from_review
from app.services.textbook_service import confirmed_chapter
from app.services.textbook_units import group_chapter_directory
from scripts.sync_updated_english import prepare_books, synchronize
from test_textbook_pipeline import environment, CHAPTER_TEXT


NINTH = '25538732ec8a26780cfad5984fea5bccd7c755aa3a78686e8b10c1f8e2863de0'


def test_new_ninth_grade_labels_source_pages_and_supplements():
    texts = [f'Unique source page {n}. '+CHAPTER_TEXT for n in range(1, 143)]
    topics = junior_english_topic_chapters(NINTH, texts)
    assert len(topics) == 56
    rows = group_chapter_directory(SimpleNamespace(subject='英语', grade='初中九年级', sha256=NINTH),
        [dict(id=i, **row) for i, row in enumerate(section_chapters_from_review(
            reviewed_junior_english_directories()[NINTH], texts, junior=True), 1)])
    assert len({row['unit_title'] for row in rows}) == 8
    assert len(rows) == 16
    assert [row['title'].split(':')[0] for row in rows[:2]] == ['Section A', 'Section B']
    assert all(row['directory_layout'] == 'sections' for row in rows)
    assert rows[0]['unit_title'] == 'UNIT 1 The Changing World (What brings about changes?)'
    grammar, reading, writing, vocabulary, project = topics[2:7]
    assert (grammar['start_page'], grammar['end_page']) == (14, 14)
    assert (reading['start_page'], reading['end_page']) == (15, 16)
    assert (writing['start_page'], writing['end_page']) == (15, 18)
    assert 'Unique source page 18.' in writing['content']
    assert 'Unique source page 19.' not in writing['content']
    assert (vocabulary['start_page'], project['start_page']) == (17, 19)
    assert topics[-1]['end_page'] == 89
    for title in ('*Reading Plus', 'Listening Scripts', 'Grammar', 'Vocabulary in Each Unit',
                  'Vocabulary A-Z', 'Vocabulary from Primary School', 'Irregular Verbs'):
        assert is_removed_chapter('英语', title, '初中九年级', NINTH)
        assert not is_removed_chapter('英语', title, '初中九年级', 'historical-edition')
    assert not is_removed_chapter('英语', grammar['title'], '初中九年级', NINTH)


def test_five_local_replacements_parse_with_exact_boundaries(tmp_path):
    source = Path(__file__).resolve().parents[2] / '教材/英语'
    if not (source / '初中英语九年级上册.pdf').is_file():
        pytest.skip('Local source textbook library is not installed')
    prepared = prepare_books(source, tmp_path)
    assert [len(book['parsed']['chapters']) for book in prepared] == [6, 6, 6, 4, 24]
    assert sum(len(book['parsed']['pages']) for book in prepared) == 500
    # Unit 3 stops before Recycle 1; the final unit stops before Revision.
    assert prepared[1]['parsed']['chapters'][2]['end_page'] == 36
    assert prepared[2]['parsed']['chapters'][-1]['end_page'] == 82
    assert prepared[3]['parsed']['chapters'][-1]['end_page'] == 46


def sample_prepared():
    return [dict(item=dict(filename='小学英语五年级上册.pdf', sha256='new-edition', replaces='old-edition'),
        metadata=filename_metadata('小学英语五年级上册.pdf'), parsed=dict(pages=[CHAPTER_TEXT],
        chapters=[dict(title='Unit 1 Different friends', parent_title='', start_page=1,
            end_page=1, printed_pages='2', content=CHAPTER_TEXT, is_published=True)]))]


@pytest.mark.asyncio
async def test_sync_retires_only_old_book_preserves_history_and_is_idempotent(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        old = Textbook(**filename_metadata('小学英语五年级上册.pdf'), sha256='old-edition',
            original_filename='小学英语五年级上册.pdf', file_path='old.pdf', page_count=1, is_published=True)
        db.add(old)
        await db.flush()
        chapter = TextbookChapter(book_id=old.id, title='Unit 1 Original', parent_title='',
            start_page=1, end_page=1, content=CHAPTER_TEXT, is_published=True)
        db.add(chapter)
        await db.flush()
        lesson = TextbookLesson(user_id=1, chapter_id=chapter.id, title='Historical lesson',
            content='Historical content', sources_json='{}')
        db.add(lesson)
        await db.commit()
        old_id, chapter_id = old.id, chapter.id
        report = await synchronize(db, sample_prepared())
        await db.commit()
        new_id = report['created_book_ids'][0]
        assert report['retired_book_ids'] == [old_id] and new_id != old_id
        assert (await db.get(TextbookChapter, chapter_id)).content == CHAPTER_TEXT
        assert lesson.chapter_id == chapter_id and lesson.content == 'Historical content'
        first_ids = [row.id for row in (await db.execute(select(TextbookChapter))).scalars()]
        second = await synchronize(db, sample_prepared())
        await db.commit()
        assert second['created_book_ids'] == second['retired_book_ids'] == []
        assert second['changed_fields'] == 0
        assert second['books'][0]['added_pages'] == second['books'][0]['added_chapters'] == 0
        assert first_ids == [row.id for row in (await db.execute(select(TextbookChapter))).scalars()]
    books = (await client.get('/textbooks')).json()['data']
    assert [book['id'] for book in books] == [new_id]
    assert (await client.get(f'/textbooks/{old_id}/chapters')).status_code == 404
    assert (await client.get(f'/textbooks/chapters/{chapter_id}')).status_code == 404
    async with sessions() as db:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await confirmed_chapter(db, chapter_id, '英语', '小学五年级')
        assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_failed_sync_rolls_back_all_books(environment):
    _, sessions, _ = environment
    prepared = sample_prepared()
    # An existing PDF with inconsistent metadata must abort the whole batch.
    async with sessions() as db:
        conflict = Textbook(title='conflict', subject='数学', grade='小学五年级', sha256='conflict',
            original_filename='conflict.pdf', file_path='conflict.pdf', is_published=True)
        db.add(conflict)
        await db.commit()
        bad = {**prepared[0], 'item': {**prepared[0]['item'], 'sha256': 'conflict'}}
        with pytest.raises(ValueError, match='conflicting subject/grade'):
            await synchronize(db, prepared+[bad])
        await db.rollback()
        assert (await db.execute(select(Textbook).where(Textbook.sha256 == 'new-edition'))).scalar_one_or_none() is None
        assert (await db.execute(select(TextbookPage))).scalars().all() == []
