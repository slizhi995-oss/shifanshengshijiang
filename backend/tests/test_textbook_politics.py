"""Regressions for the source book's unit, lesson and topic boundaries."""
import hashlib
from pathlib import Path

import fitz
import pytest

from app.models.textbook import Textbook, TextbookChapter
from app.services import textbook_units as units
from app.services.textbook_outline import compact, contents_entries, extract_outline, reviewed_directory
from test_textbook_pipeline import environment


DIGEST = '303dc526d8ce8de16b6b81752f8f4030819eadca5b093284c74603bd1292f347'


def source_chapters():
    source = Path(__file__).resolve().parents[2]/'教材'/'政治'/'高中政治必修二.pdf'
    if not source.exists():
        pytest.skip('Local source textbook is not installed')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == DIGEST
    review = reviewed_directory(DIGEST)
    with fitz.open(source) as document:
        _, chapters, _ = extract_outline(document, '政治', review['entries'],
                                         review['contents_pages'], review['offset'], grade='高中')
    return chapters


def test_directory_footer_is_not_an_entry_or_a_unit_start():
    def line(text, y, x=40, right=550):
        return dict(text=text, x=x, right=right, y=y, top=y-8, size=12)
    lines = [line('第二单元 经济发展与社会进步', 80), line('31', 80, 520),
             line('第三课 我国的经济发展', 120), line('32', 120, 520),
             line('目录', 790, 480), line('1', 790, 520)]
    assert [entry['printed'] for entry in contents_entries(lines, 600, 840)] == [31, 32]
    assert units.directory_units(lines, 600, 840) == [dict(title='第二单元 经济发展与社会进步', printed=31)]


def test_reviewed_unit_boundaries_override_native_reparsing(monkeypatch):
    review = reviewed_directory(DIGEST)
    monkeypatch.setattr(units, 'reviewed_directory', lambda _: review)
    def unexpected_open(*args, **kwargs):
        raise AssertionError('Reviewed units should not be reinterpreted')
    monkeypatch.setattr(units.fitz, 'open', unexpected_open)
    rows = units.source_units('missing-politics.pdf', 0, 'reviewed-unit-regression')
    assert [row['printed'] for row in rows] == [1, 31]


def test_source_lessons_contain_both_topics_and_inquiries_remain_separate():
    rows = source_chapters()
    assert len(rows) == 16
    lessons = [rows[i] for i in (1, 4, 9, 12)]
    assert [(row['start_page'], row['end_page']) for row in lessons] == [(6, 17), (18, 29), (36, 47), (48, 60)]
    for lesson, topic_indexes in zip(lessons, ((2, 3), (5, 6), (10, 11), (13, 14))):
        assert not lesson['parent_title']
        for i in topic_indexes:
            assert rows[i]['parent_title'] == lesson['title']
            assert compact(rows[i]['title']) in compact(lesson['content'])
    assert not rows[7]['parent_title'] and not rows[15]['parent_title']
    assert [row['is_published'] for row in rows] == [True]*16
    assert all('is_nested' not in row for row in rows)  # Persistable model fields only.


@pytest.mark.asyncio
async def test_student_api_preserves_source_order_groups_and_topic_indentation(environment):
    client, sessions, _ = environment
    chapters = source_chapters()
    async with sessions() as db:
        book = Textbook(title='必修二', subject='政治', grade='高中', file_path='missing.pdf',
                        original_filename='高中政治必修二.pdf', sha256=DIGEST, page_count=69,
                        is_published=True)
        db.add(book)
        await db.flush()
        # Historic IDs need not follow source order for same-page entries.
        db.add_all(TextbookChapter(book_id=book.id, **row) for row in reversed(chapters))
        await db.commit()
        identifier = book.id
    response = await client.get(f'/textbooks/{identifier}/chapters')
    assert response.status_code == 200
    rows = response.json()['data']
    assert [row['title'] for row in rows] == [row['title'] for row in chapters]
    assert [row['unit_title'] for row in rows] == ['第一单元 生产资料所有制与经济体制']*8 + ['第二单元 经济发展与社会进步']*8
    assert [i for i, row in enumerate(rows) if row['is_nested']] == [2, 3, 5, 6, 10, 11, 13, 14]
