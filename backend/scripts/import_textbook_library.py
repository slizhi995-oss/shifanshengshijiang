"""Import the filename-organized textbook library without replacing historical IDs.

From backend: python -m scripts.import_textbook_library --source ../教材
Add --apply to write PDFs and parsed text to the configured database/storage.
The default is a read-only survey; parse caches/reports live under outputs/.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import fitz
from sqlalchemy import select, func

from app.core.database import engine, async_session_factory
from app.models.base import Base
from app.models.textbook import Textbook, TextbookPage, TextbookChapter
from app.services.textbook_catalog import filename_metadata, school_stage, clean_chapter_title, is_removed_chapter
from app.services.textbook_outline import extract_outline, reviewed_directory
from app.services.textbook_service import private_path
from app.services.textbook_physics import stored_physics_directory

PARSER_VERSION = 8


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parse(path, sha, output):
    metadata = filename_metadata(path.name)
    cache = output / 'cache' / f'{sha}-v{PARSER_VERSION}.json'
    if cache.exists():
        result = json.loads(cache.read_text(encoding='utf-8'))
        subject = metadata['subject']
        result['chapters'] = [chapter for chapter in result['chapters'] if not is_removed_chapter(subject, chapter['title'], metadata['grade'], sha)]
        if subject == '物理':
            result['chapters'] = stored_physics_directory(SimpleNamespace(**metadata), result['chapters'])
        if subject == '政治' and metadata['grade'].startswith('高中'):
            from app.services.textbook_politics import politics_chapter_hierarchy
            result['chapters'] = politics_chapter_hierarchy(result['chapters'], result['pages'])
        if subject == '化学' and metadata['grade'].startswith('高中') and 'pages' in result:
            from app.services.textbook_chemistry import chemistry_chapter_hierarchy
            result['chapters'] = chemistry_chapter_hierarchy(result['chapters'], result['pages'], reviewed_directory(sha))
        if subject == '英语' and metadata['grade'].startswith('高中') and 'pages' in result:
            from app.services.textbook_english import expand_english_chapters
            result['chapters'] = expand_english_chapters(sha, result['chapters'], result['pages'])
        if subject == '英语' and metadata['grade'].startswith('初中') and 'pages' in result:
            from app.services.textbook_junior_english import expand_junior_english_chapters
            result['chapters'] = expand_junior_english_chapters(sha, result['chapters'], result['pages'])
        if subject == '英语' and metadata['grade'].startswith('小学') and 'pages' in result:
            from app.services.textbook_primary_english import expand_primary_english_chapters
            result['chapters'] = expand_primary_english_chapters(sha, result['chapters'], result['pages'])
        return result
    with fitz.open(path) as document:
        if document.needs_pass or not 1 <= len(document) <= 1000:
            raise ValueError('教材须为未加密、1–1000页的PDF')
        review=reviewed_directory(sha)
        pages, chapters, diagnostics = extract_outline(document, filename_metadata(path.name)['subject'],
            review['entries'] if review else None,review['contents_pages'] if review else None,review['offset'] if review else None,
            grade=metadata['grade'])
    nonempty = sum(len(text.strip()) >= 20 for text in pages)
    subject = filename_metadata(path.name)['subject']
    chapters = [chapter for chapter in chapters if not is_removed_chapter(subject, chapter['title'], metadata['grade'], sha)]
    if subject == '物理':
        chapters = stored_physics_directory(SimpleNamespace(**metadata), chapters)
    if subject == '英语' and metadata['grade'].startswith('高中'):
        from app.services.textbook_english import expand_english_chapters
        chapters = expand_english_chapters(sha, chapters, pages)
    if subject == '英语' and metadata['grade'].startswith('初中'):
        from app.services.textbook_junior_english import expand_junior_english_chapters
        chapters = expand_junior_english_chapters(sha, chapters, pages)
    if subject == '英语' and metadata['grade'].startswith('小学'):
        from app.services.textbook_primary_english import expand_primary_english_chapters
        chapters = expand_primary_english_chapters(sha, chapters, pages)
    status = 'needs_ocr' if nonempty < len(pages)*.3 else 'ready' if any(c['is_published'] for c in chapters) else 'needs_chapters'
    result = dict(pages=pages, chapters=chapters, status=status, diagnostics=diagnostics,
                  text_pages=nonempty)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result


def backup_sqlite(output):
    if engine.url.get_backend_name() != 'sqlite':
        raise RuntimeError('此批量写入脚本需要SQLite自动备份；其他数据库须另行配置备份')
    source = Path(engine.url.database).resolve()
    if not source.exists():
        return None
    backup = output / f'database-before-{datetime.now():%Y%m%d-%H%M%S-%f}.db'
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as original, sqlite3.connect(backup) as target:
        original.backup(target)
    return str(backup.resolve())


async def import_book(path, sha, metadata, parsed):
    async with async_session_factory() as db:
        book = (await db.execute(select(Textbook).where(Textbook.sha256 == sha))).scalar_one_or_none()
        existing = book is not None
        if not book:
            relative = f'library/{sha}/original.pdf'
            target = private_path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or digest(target) != sha:
                temporary = target.with_suffix('.pdf.tmp')
                shutil.copyfile(path, temporary)
                if digest(temporary) != sha:
                    raise ValueError('复制后的PDF校验失败')
                temporary.replace(target)
            book = Textbook(**metadata, file_path=relative, original_filename=path.name, sha256=sha,
                            page_count=len(parsed['pages']), status=parsed['status'], is_published=True)
            db.add(book)
            await db.flush()
            db.add_all(TextbookPage(book_id=book.id, page_number=i, content=text)
                       for i, text in enumerate(parsed['pages'], 1))
        else:
            if book.subject != metadata['subject'] or school_stage(book.grade) != school_stage(metadata['grade']):
                raise ValueError('同一PDF已有不同科目/学段，需先核对，未覆盖旧记录')
            book.title = metadata['title']
            book.grade = metadata['grade']
            book.volume = metadata['volume']
            book.original_filename = path.name
            book.is_published = True
            if not private_path(book.file_path).is_file():
                private_path(book.file_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, private_path(book.file_path))
        old = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id))).scalars().all()
        # A reviewed historical outline and its images/lessons take priority.
        if not any(chapter.is_published for chapter in old):
            keys = {(chapter.start_page, clean_chapter_title(chapter.title)) for chapter in old}
            for chapter in parsed['chapters']:
                if is_removed_chapter(book.subject, chapter['title'], book.grade, book.sha256):
                    continue
                chapter = {**chapter, 'title': clean_chapter_title(chapter['title']),
                           'parent_title': clean_chapter_title(chapter.get('parent_title', ''))}
                if (chapter['start_page'], chapter['title']) not in keys:
                    db.add(TextbookChapter(book_id=book.id, **chapter))
        await db.commit()
        count = (await db.execute(select(func.count()).select_from(TextbookChapter).where(
            TextbookChapter.book_id == book.id, TextbookChapter.is_published == True))).scalar_one()
        return dict(book_id=book.id, reused=existing, published_chapters=count)


async def main(source, output, apply):
    source, output = source.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    files = sorted(source.rglob('*.pdf'))
    if not files:
        raise ValueError('教材目录没有PDF')
    # Validate all names/hashes before any database mutation.
    catalog, hashes = [], {}
    for path in files:
        metadata = filename_metadata(path.name)
        sha = digest(path)
        if sha in hashes:
            raise ValueError(f'不同教材文件内容重复，请先核对：{hashes[sha]} / {path.name}')
        hashes[sha] = path.name
        catalog.append((path, sha, metadata))
    report = dict(source=str(source), apply=apply, files=len(files), books=[], errors=[])
    if apply:
        report['database_backup'] = backup_sqlite(output)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    try:
        for number, (path, sha, metadata) in enumerate(catalog, 1):
            try:
                parsed = await asyncio.to_thread(parse, path, sha, output)
                row = dict(file=path.name, sha256=sha, **metadata, pages=len(parsed['pages']),
                           text_pages=parsed['text_pages'], status=parsed['status'],
                           chapters=len(parsed['chapters']), published_chapters=sum(c['is_published'] for c in parsed['chapters']),
                           diagnostics=parsed['diagnostics'])
                if apply:
                    row.update(await import_book(path, sha, metadata, parsed))
                report['books'].append(row)
                print(f"[{number}/{len(files)}] {path.name}: {row['pages']}页 / {row['published_chapters']}章节 / {row['status']}", flush=True)
            except Exception as exc:
                report['errors'].append(dict(file=path.name, error=str(exc)))
                print(f'ERROR {path.name}: {exc}', flush=True)
            (output / ('import-report.json' if apply else 'parse-report.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        await engine.dispose()
    if report['errors']:
        raise RuntimeError(f"{len(report['errors'])}份教材失败，详见报告")
    print(json.dumps(dict(files=len(report['books']), pages=sum(b['pages'] for b in report['books']),
                          chapters=sum(b['published_chapters'] for b in report['books']),
                          needs_attention=[b['file'] for b in report['books'] if not b['published_chapters']]), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('../教材'))
    parser.add_argument('--output', type=Path, default=Path('outputs/textbook-library'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    asyncio.run(main(args.source, args.output, args.apply))
