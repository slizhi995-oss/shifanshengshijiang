"""Section migration preserves history, exact page sets and image access."""
import pytest
from types import SimpleNamespace
from sqlalchemy import select

from app.models.textbook import Textbook, TextbookChapter, TextbookLesson, TextbookPage, TextbookAsset
from app.services.textbook_english import reviewed_english_directories
from app.services.textbook_junior_english import reviewed_junior_english_directories
from app.services.textbook_english_sections import section_chapters_from_review, english_section_pages
from app.services.textbook_service import chapter_assets, confirmed_chapter
from scripts.merge_english_sections import synchronize
from test_textbook_pipeline import environment, CHAPTER_TEXT


JUNIOR = '23931ae73882e93c213b28fb32a713e1fd312bb6d3f22abe7d34625375c444a9'
HIGH = 'fe798cdc7010b208a1fa952f3eb4c60d853e50e745908b27e7dc89ad01b7d906'


def test_highschool_reading_extraction_skips_pages_between_main_book_and_workbook():
    chapter = SimpleNamespace(parent_title='UNIT 1 TEENAGE LIFE', title='Reading')
    assert english_section_pages(SimpleNamespace(subject='英语', grade='高中', sha256=HIGH), chapter) == [19, 20, 23, 24, 79]


def test_uploaded_animal_friends_has_only_two_selectable_sections_with_complete_text():
    texts = [f'Unique page {page}. {CHAPTER_TEXT}' for page in range(1, 155)]
    review = reviewed_junior_english_directories()[JUNIOR]
    rows = section_chapters_from_review(review, texts, junior=True)
    a, b = rows[:2]
    assert a['parent_title'] == b['parent_title'] == 'UNIT 1 Animal Friends (Why are animals important?)'
    assert a['title'] == 'Section A: Why do you like animals?'
    assert b['title'] == 'Section B: How are animals part of our lives?'
    for row, section in zip((a, b), review['units'][0]['sections'][:2]):
        pages = sorted({page + review['offset'] for item in section['items']
                        for page in range(item['pages'][0], item['pages'][1] + 1)})
        assert row['content'] == '\n\n'.join(f'[PDF第{page}页]\n{texts[page-1]}' for page in pages)
    assert len(rows) == 16


@pytest.mark.asyncio
async def test_merge_is_idempotent_keeps_historical_lesson_and_reuses_unit_images(environment):
    client, sessions, _ = environment
    async with sessions() as db:
        book = Textbook(title='七年级下册', subject='英语', grade='初中七年级', sha256=JUNIOR,
            original_filename='初中英语七年级下册.pdf', file_path='missing.pdf', page_count=154, is_published=True)
        db.add(book)
        await db.flush()
        db.add_all([TextbookPage(book_id=book.id, page_number=page, content=CHAPTER_TEXT) for page in range(1, 155)])
        unit = TextbookChapter(book_id=book.id, title='Unit 1 Animal Friends', parent_title='',
            start_page=10, end_page=17, content=CHAPTER_TEXT, is_published=True)
        task = TextbookChapter(book_id=book.id, title='Speaking: Talk about your favourite animals',
            parent_title='UNIT 1 Animal Friends (Why are animals important?) · Section A: Why do you like animals?',
            start_page=11, end_page=13, content=CHAPTER_TEXT, is_published=True)
        db.add_all([unit, task])
        await db.flush()
        lesson = TextbookLesson(user_id=1, chapter_id=task.id, title='Saved lesson', content='Saved body', sources_json='{}')
        db.add(lesson)
        for n, page in enumerate((11, 80), 1):
            db.add(TextbookAsset(asset_id=f'tb-{n:032x}', book_id=book.id, chapter_id=unit.id,
                title='Source image', file_path=f'{n}.png', pdf_page=page, width=240, height=140,
                sha256=str(n)*64, is_reviewed=True))
        await db.commit()
        task_id, unit_id, lesson_id = task.id, unit.id, lesson.id
        report = await synchronize(db)
        await db.commit()
        assert report['added'] == 16 and report['hidden'] == 1
        assert (await db.get(TextbookChapter, task_id)).content == CHAPTER_TEXT
        assert not (await db.get(TextbookChapter, task_id)).is_published
        assert (await db.get(TextbookChapter, unit_id)).is_published
        assert (await db.get(TextbookLesson, lesson_id)).chapter_id == task_id
        chapters = (await client.get(f'/textbooks/{book.id}/chapters')).json()['data']
        choices = [row for row in chapters if not row['is_unit']]
        assert len(choices) == 16
        first, _ = await confirmed_chapter(db, choices[0]['id'], '英语', '初中')
        assert first.title == 'Section A: Why do you like animals?'
        images = await chapter_assets(db, first, book)
        assert [image['pdf_page'] for image in images] == [11]
        ids = [row['id'] for row in choices]
        second = await synchronize(db)
        await db.commit()
        assert second['added'] == second['hidden'] == second['updated_fields'] == 0
        assert ids == [row['id'] for row in (await client.get(f'/textbooks/{book.id}/chapters')).json()['data'] if not row['is_unit']]


@pytest.mark.asyncio
async def test_incomplete_second_book_rolls_back_first_book(environment):
    _, sessions, _ = environment
    async with sessions() as db:
        for digest, grade in ((JUNIOR, '初中'), (HIGH, '高中')):
            book = Textbook(title='Source', subject='英语', grade=grade, sha256=digest,
                original_filename='source.pdf', file_path='missing.pdf', page_count=154, is_published=True)
            db.add(book)
            await db.flush()
            if digest == JUNIOR:
                db.add_all([TextbookPage(book_id=book.id, page_number=page, content=CHAPTER_TEXT) for page in range(1, 155)])
        await db.commit()
        with pytest.raises(ValueError, match='Incomplete source pages'):
            await synchronize(db)
        await db.rollback()
        assert (await db.execute(select(TextbookChapter))).scalars().all() == []
