"""Sync the five reviewed English replacements in one database transaction.

From backend: python -m scripts.sync_updated_english [--apply]
Old editions are unpublished, with all historical IDs and references retained.
The default validates local PDFs and previews the exact database changes.
"""
import argparse
import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookPage
from app.services.textbook_catalog import filename_metadata
from app.services.textbook_outline import reviewed_directory
from app.services.textbook_primary_english import reviewed_flat_primary_english_directory
from app.services.textbook_service import private_path
from app.services.textbook_units import group_chapter_directory
from scripts.import_textbook_library import backup_sqlite, digest, parse


MANIFEST_PATH = Path(__file__).resolve().parents[1] / 'app/data/english_refresh_20261021.json'


def prepare_books(source, output):
    """Validate every hash, teaching boundary and display row before writing."""
    prepared = []
    for item in json.loads(MANIFEST_PATH.read_text(encoding='utf8')):
        path = source / item['filename']
        if digest(path) != item['sha256']:
            raise ValueError(f'PDF differs from reviewed edition: {path.name}')
        metadata = filename_metadata(path.name)
        parsed = parse(path, item['sha256'], output)
        chapters = parsed['chapters']
        if parsed['status'] != 'ready' or len(chapters) != item['chapters']:
            raise ValueError(f'Incomplete reviewed directory: {path.name}')
        if any(not row['is_published'] or not 1 <= row['start_page'] <= row['end_page'] <= len(parsed['pages'])
               or max(len(row['title']), len(row.get('parent_title', ''))) > 160 for row in chapters):
            raise ValueError(f'Invalid reviewed chapter: {path.name}')
        keys = [(row.get('parent_title', ''), row['title']) for row in chapters]
        if len(set(keys)) != len(keys):
            raise ValueError(f'Duplicate reviewed chapter: {path.name}')
        rows = [dict(id=index, book_id=0, **row) for index, row in enumerate(chapters, 1)]
        book = SimpleNamespace(sha256=item['sha256'], **metadata)
        if len(group_chapter_directory(book, rows)) != item['chapters']:
            raise ValueError(f'Incomplete frontend directory: {path.name}')
        # Supplements must still delimit the last unit even though they are
        # excluded from selectable rows. Never let it absorb revision/appendices.
        review = reviewed_directory(item['sha256'])
        if metadata['grade'].startswith('小学'):
            allowed = {entry['title'] for entry in reviewed_flat_primary_english_directory(item['sha256'])['entries']}
            for row in chapters:
                pos = next(i for i, entry in enumerate(review['entries']) if entry['title'] == row['title'])
                expected_end = review['entries'][pos+1]['printed'] + review['offset'] - 1
                if row['title'] not in allowed or row['end_page'] != expected_end:
                    raise ValueError(f'Incorrect primary unit boundary: {path.name}: {row["title"]}')
        metadata.update(publisher='人民教育出版社', edition='精通' if '六年级上册' in path.name else
                        'PEP' if metadata['grade'].startswith('小学') else '')
        prepared.append(dict(item=item, path=path, metadata=metadata, parsed=parsed))
    return prepared


def update_fields(target, values):
    count = 0
    for field, value in values.items():
        if getattr(target, field) != value:
            setattr(target, field, value)
            count += 1
    return count


async def synchronize(db, prepared):
    """Caller owns the transaction, allowing a true preview via rollback."""
    report = dict(books=[], changed_fields=0, created_book_ids=[], retired_book_ids=[])
    for entry in prepared:
        item, metadata, parsed = entry['item'], entry['metadata'], entry['parsed']
        book = (await db.execute(select(Textbook).where(Textbook.sha256 == item['sha256']))).scalar_one_or_none()
        created = book is None
        if created:
            book = Textbook(**metadata, sha256=item['sha256'], original_filename=item['filename'],
                file_path=f'library/{item["sha256"]}/original.pdf', page_count=len(parsed['pages']),
                status='ready', is_published=True)
            db.add(book)
            await db.flush()
            report['created_book_ids'].append(book.id)
        else:
            if book.subject != metadata['subject'] or book.grade != metadata['grade']:
                raise ValueError(f'Existing edition has conflicting subject/grade: {book.id}')
            report['changed_fields'] += update_fields(book, dict(**metadata, original_filename=item['filename'],
                page_count=len(parsed['pages']), status='ready', is_published=True))
        pages = {row.page_number: row for row in (await db.execute(select(TextbookPage).where(
            TextbookPage.book_id == book.id))).scalars()}
        added_pages = 0
        for number, text in enumerate(parsed['pages'], 1):
            if number not in pages:
                db.add(TextbookPage(book_id=book.id, page_number=number, content=text))
                added_pages += 1
            else:
                report['changed_fields'] += update_fields(pages[number], dict(content=text))
        if set(pages) - set(range(1, len(parsed['pages'])+1)):
            raise ValueError(f'Unexpected stored PDF pages: {book.id}')
        existing = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id))).scalars().all()
        keys = {(row.parent_title, row.title): row for row in existing}
        if len(keys) != len(existing):
            raise ValueError(f'Duplicate stored chapters: {book.id}')
        expected, added_chapters = set(), 0
        for row in parsed['chapters']:
            key = (row.get('parent_title', ''), row['title'])
            expected.add(key)
            if key not in keys:
                db.add(TextbookChapter(book_id=book.id, **row))
                added_chapters += 1
            else:
                report['changed_fields'] += update_fields(keys[key], row)
        for key, chapter in keys.items():
            if key not in expected:
                report['changed_fields'] += update_fields(chapter, dict(is_published=False))
        old = (await db.execute(select(Textbook).where(Textbook.sha256 == item['replaces']))).scalar_one_or_none()
        if old is not None:
            if old.subject != metadata['subject'] or old.grade != metadata['grade']:
                raise ValueError(f'Historical edition has conflicting subject/grade: {old.id}')
            if old.is_published:
                report['changed_fields'] += update_fields(old, dict(is_published=False))
                report['retired_book_ids'].append(old.id)
        report['books'].append(dict(book_id=book.id, filename=item['filename'], sha256=item['sha256'],
            old_book_id=old.id if old else None, created=created, pages=len(parsed['pages']),
            chapters=len(parsed['chapters']), added_pages=added_pages, added_chapters=added_chapters))
    await db.flush()
    return report


async def main(source, output, apply=False):
    source, output = source.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        prepared = prepare_books(source, output)
        backup = backup_sqlite(output) if apply else None
        if apply:
            for entry in prepared:
                item = entry['item']
                target = private_path(f'library/{item["sha256"]}/original.pdf')
                if target.exists() and digest(target) == item['sha256']:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix('.pdf.tmp')
                shutil.copyfile(entry['path'], temporary)
                if digest(temporary) != item['sha256']:
                    raise ValueError(f'Copied PDF checksum mismatch: {item["filename"]}')
                temporary.replace(target)
        async with async_session_factory() as db:
            report = await synchronize(db, prepared)
            if apply:
                await db.commit()
            else:
                await db.rollback()
        report.update(applied=apply, database_backup=backup)
        report_path = output / f'{"applied" if apply else "preview"}-{datetime.now():%Y%m%d-%H%M%S-%f}.json'
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('../教材/英语'))
    parser.add_argument('--output', type=Path, default=Path('outputs/english-refresh-20261021'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    asyncio.run(main(args.source, args.output, args.apply))
