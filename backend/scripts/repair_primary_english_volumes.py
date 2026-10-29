"""Align the three audited lower-volume PDFs with their current local filenames.

From backend: python -m scripts.repair_primary_english_volumes [--apply]
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

import fitz
from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook
from app.services.textbook_catalog import filename_metadata
from app.services.textbook_outline import reviewed_directory
from app.services.textbook_service import private_path
from scripts.import_textbook_library import backup_sqlite, digest


VOLUMES = {
    '20d8721c3e613f007a1a2b6c7c5cb5ca5786e4a5b14e0bb0197c8017bf148499': '小学英语四年级下册.pdf',
    'dd7c53639a9e54dc36b552ec92dab0443536c4ea3c80842c3fa3dd7c2ef5ef1e': '小学英语五年级下册.pdf',
    '0411b214adcca507dd9699d5872cf173a2c226a16e11655717f199b483f38d91': '小学英语六年级下册.pdf',
}


async def main(apply=False, source=Path('../教材/英语')):
    output = Path('outputs/primary-english-volumes')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, books=[], changes=[])
    try:
        async with async_session_factory() as db:
            # Check all three sources before changing any record.
            for sha, filename in VOLUMES.items():
                path = source/filename
                if not path.is_file() or digest(path) != sha:
                    raise ValueError(f'Local PDF does not match audited volume: {filename}')
                if reviewed_directory(sha)['filename'] != filename:
                    raise ValueError(f'Reviewed directory filename mismatch: {filename}')
                book = (await db.execute(select(Textbook).where(Textbook.sha256 == sha))).scalar_one()
                if book.subject != '英语' or not book.grade.startswith('小学'):
                    raise ValueError(f'Unexpected subject/stage for book {book.id}')
                stored = private_path(book.file_path)
                if not stored.is_file() or digest(stored) != sha:
                    raise ValueError(f'Stored PDF does not match audited volume: {book.id}')
                metadata = filename_metadata(filename)
                with fitz.open(path) as pdf:
                    title_page = ''.join(pdf[1].get_text().split())
                    if len(pdf) != book.page_count or metadata['title'] not in title_page:
                        raise ValueError(f'PDF title/page count mismatch: {filename}')
                expected = {field: metadata[field] for field in ('title', 'grade', 'volume')}
                expected['original_filename'] = filename
                for field, value in expected.items():
                    if getattr(book, field) != value:
                        report['changes'].append(dict(id=book.id, field=field,
                            before=getattr(book, field), after=value))
                report['books'].append(dict(id=book.id, sha256=sha, **expected))
            if apply and report['changes']:
                report['database_backup'] = backup_sqlite(output)
                (output/f'recovery-{datetime.now():%Y%m%d-%H%M%S-%f}.json').write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
                for change in report['changes']:
                    setattr(await db.get(Textbook, change['id']), change['field'], change['after'])
                await db.commit()
            (output/('applied.json' if apply else 'preview.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps(dict(applied=apply, books=report['books'], changed_fields=len(report['changes']),
                database_backup=report.get('database_backup')), ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--source', type=Path, default=Path('../教材/英语'))
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.source))
