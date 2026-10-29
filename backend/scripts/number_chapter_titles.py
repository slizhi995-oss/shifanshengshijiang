"""Restore chapter labels from their printed directories without inventing numbers.

Run from backend: python -m scripts.number_chapter_titles [--apply]
Labels are restored and duplicate/mixed directory rows are unpublished.
The database is backed up before applying; IDs and lesson/material bindings stay intact.
"""
import argparse
import asyncio
import json
import re
from collections import defaultdict
from pathlib import Path

import fitz
from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter
from app.services.textbook_catalog import clean_chapter_title, numbered_chapter_title, has_chapter_number
from app.services.textbook_outline import contents_entries, page_lines, reviewed_directory, title_key, compact, reconcile_directory_entries
from app.services.textbook_service import private_path
from scripts.import_textbook_library import backup_sqlite


def proposed_titles(book, chapters):
    if not chapters:
        return
    review = reviewed_directory(book.sha256)
    order = {(e['printed'] + review['offset'], title_key(e['title'])): i
             for i, e in enumerate(review['entries'])} if review else {}
    chapters = sorted(chapters, key=lambda c: (c.start_page,
        order.get((c.start_page, title_key(c.title)), len(order)), c.id))
    native = []
    source = private_path(book.file_path)
    if source.is_file():
        with fitz.open(source) as document:
            pages = review['contents_pages'] if review else range(1, min(22, len(document)) + 1)
            for number in pages:
                page = document[number - 1]
                native.extend(contents_entries(page_lines(page), page.rect.width, page.rect.height))
    entries = reconcile_directory_entries(review['entries'], native) if review else native
    recovered = {}
    for entry in entries:
        for title in [entry['title'], *entry.get('source_aliases', [])]:
            recovered.setdefault((str(entry['printed']), title_key(title)), entry['title'])
    for position, chapter in enumerate(chapters, 1):
        original = clean_chapter_title(chapter.title).strip()
        title = original
        printed = re.match(r'\s*(\d+)', chapter.printed_pages)
        candidate = recovered.get((printed[1] if printed else '', title_key(original)))
        if candidate is None and review:
            # Some old rows omitted printed_pages but still have the audited PDF boundary.
            candidate = recovered.get((str(chapter.start_page-review['offset']), title_key(original)))
        if candidate is not None and candidate.count('*') == original.count('*'):
            title = candidate
        yield chapter, numbered_chapter_title(title, position)


def duplicate_rows(book, proposals):
    review = reviewed_directory(book.sha256)
    if not review:
        return []
    source = {(entry['printed']+review['offset'], title_key(entry['title'])) for entry in review['entries']}
    confirmed = defaultdict(list)
    for chapter, title in proposals:
        if chapter.is_published and (chapter.start_page, title_key(title)) in source:
            confirmed[(chapter.start_page, title)].append(chapter)
    hidden = []
    for (_, title), candidates in confirmed.items():
        # Keep the complete original row, preserving every duplicate's ID in drafts.
        ordered = sorted(candidates, key=lambda c: (title_key(c.title) != title_key(title), -len(c.title), c.id))
        hidden.extend(dict(id=c.id, book_id=book.id, title=c.title, reason='duplicate directory row') for c in ordered[1:])
    for chapter, title in proposals:
        if not chapter.is_published or (chapter.start_page, title_key(title)) in source:
            continue
        key = compact(title)
        if any(0 <= start-chapter.start_page <= 1 and key.endswith(compact(label)) and len(compact(label)) >= 4
               for start, label in confirmed):
            hidden.append(dict(id=chapter.id, book_id=book.id, title=chapter.title, reason='mixed with preceding directory row'))
    return hidden


async def main(apply=False):
    output = Path('outputs/chapter-numbering')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, changes=[], hide=[])
    try:
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).order_by(Textbook.id))).scalars().all()
            chapters = (await db.execute(select(TextbookChapter))).scalars().all()
            grouped = defaultdict(list)
            for chapter in chapters:
                grouped[chapter.book_id].append(chapter)
            for book in books:
                proposals = list(proposed_titles(book, grouped[book.id]))
                report['hide'].extend(duplicate_rows(book, proposals))
                for chapter, title in proposals:
                    if title != chapter.title:
                        assert title.count('*') == chapter.title.count('*')
                        report['changes'].append(dict(id=chapter.id, book_id=book.id, field='title', before=chapter.title, after=title))
                for chapter in grouped[book.id]:
                    parent = numbered_chapter_title(chapter.parent_title, 0)
                    if parent != chapter.parent_title:
                        report['changes'].append(dict(id=chapter.id, book_id=book.id, field='parent_title', before=chapter.parent_title, after=parent))
            if apply and (report['changes'] or report['hide']):
                report['database_backup'] = backup_sqlite(output)
                by_id = {c.id: c for c in chapters}
                for change in report['changes']:
                    setattr(by_id[change['id']], change['field'], change['after'])
                for change in report['hide']:
                    by_id[change['id']].is_published = False
                await db.commit()
            report['chapters_changed'] = len({c['id'] for c in report['changes']})
            report['books_changed'] = len({c['book_id'] for c in report['changes']})
            report['duplicates_unpublished'] = len(report['hide'])
            (output / ('applied.json' if apply else 'preview.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: v for k, v in report.items() if k not in ('changes', 'hide')}, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
