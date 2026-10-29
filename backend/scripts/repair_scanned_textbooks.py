"""Recover missing scanned-textbook chapters locally; cache OCR and back up writes.

From backend: python -m scripts.repair_scanned_textbooks [--front-only] [--apply]
Only published books marked needs_ocr with no existing chapters are eligible.
Install optional dependencies from requirements-ocr.txt before running.
"""
import argparse
import asyncio
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import fitz
from sqlalchemy import select, func

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookPage, TextbookChapter
from app.services.textbook_service import private_path
from app.services.textbook_ocr import OCRDocument, recognize_page
from app.services.textbook_outline import extract_outline
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_physics import stored_physics_directory
from scripts.import_textbook_library import backup_sqlite
from scripts.scanned_textbook_contents import reviewed_contents, PDF_OFFSETS

OUTPUT = Path('outputs/scanned-textbook-repair')


def recognize_book(book, front_only):
    from rapidocr_onnxruntime import RapidOCR
    recognizer = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1, det_limit_side_len=1200)
    root = OUTPUT/'cache'/book['sha256']
    root.mkdir(parents=True, exist_ok=True)
    pages = []
    with fitz.open(book['path']) as document:
        count = min(14, len(document)) if front_only else len(document)
        for index in range(count):
            cache = root/f'{index+1:04d}.json'
            if cache.exists():
                page = json.loads(cache.read_text(encoding='utf-8-sig'))
            else:
                page = recognize_page(document[index], recognizer)
                cache.write_text(json.dumps(page, ensure_ascii=False), encoding='utf-8')
            pages.append(page)
            if (index+1) % 20 == 0 or index+1 == count:
                print(f"OCR book={book['id']} pages={index+1}/{count}", flush=True)
    contents, toc_pages = reviewed_contents(book)
    texts, chapters, diagnostics = extract_outline(OCRDocument(pages), book['subject'], contents, toc_pages, PDF_OFFSETS.get(book['filename']), grade=book.get('grade', ''))
    if not front_only and book['subject'] == '英语' and book.get('grade', '').startswith('高中'):
        from app.services.textbook_english import expand_english_chapters
        chapters = expand_english_chapters(book['sha256'], chapters, texts)
    texts = ['[扫描教材OCR识别正文，公式、单位及单词请对照原PDF核对]\n'+text if text.strip() else '' for text in texts]
    for chapter in chapters:
        chapter['content'] = '\n\n'.join(f'[PDF第{number}页]\n{texts[number-1]}' for number in range(chapter['start_page'],chapter['end_page']+1))
        chapter['is_published'] = chapter['is_published'] and len(chapter['content']) <= 48000
    result = dict(book=book, pages=texts, chapters=chapters, diagnostics=diagnostics)
    (OUTPUT/f"book-{book['id']}{'-front' if front_only else ''}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def prepare_windows(book):
    root = (OUTPUT/'cache'/book['sha256']).resolve()
    root.mkdir(parents=True, exist_ok=True)
    jobs = []
    with fitz.open(book['path']) as document:
        for index, page in enumerate(document, 1):
            output = root/f'{index:04d}.json'
            if output.exists():
                continue
            image = root/f'{index:04d}.png'
            scale = min(3, 2400/max(page.rect.width, page.rect.height))
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(image)
            jobs.append(dict(image=str(image), output=str(output), scale=scale,
                width=page.rect.width, height=page.rect.height, page=index))
    manifest = (OUTPUT/f"windows-{book['id']}.json").resolve()
    manifest.write_text(json.dumps(jobs), encoding='utf-8')
    print(str(manifest), flush=True)
    return len(jobs)


async def apply_result(result):
    book_id = result['book']['id']
    async with async_session_factory() as db:
        book = await db.get(Textbook, book_id)
        count = (await db.execute(select(func.count()).select_from(TextbookChapter).where(TextbookChapter.book_id==book_id))).scalar_one()
        if count or book.status != 'needs_ocr' or book.sha256 != result['book']['sha256']:
            raise ValueError(f'Book {book_id} changed since audit; refusing to replace chapters')
        if not any(chapter['is_published'] for chapter in result['chapters']):
            raise ValueError(f'Book {book_id} has no corroborated OCR chapters')
        pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id==book_id).order_by(TextbookPage.page_number))).scalars().all()
        if len(pages) != len(result['pages']):
            raise ValueError('OCR page count does not match stored original')
        for page, text in zip(pages, result['pages']):
            page.content = text
        chapters = result['chapters']
        if book.subject == '物理':
            chapters = stored_physics_directory(book, chapters)
        db.add_all(TextbookChapter(book_id=book_id, **chapter) for chapter in chapters
                   if not is_removed_chapter(book.subject, chapter['title'], book.grade))
        book.status = 'ready'
        await db.commit()


async def main(args):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_session_factory() as db:
        books = (await db.execute(select(Textbook).where(Textbook.status=='needs_ocr', Textbook.is_published==True))).scalars().all()
        targets = []
        for book in books:
            if args.books and book.id not in args.books:
                continue
            count = (await db.execute(select(func.count()).select_from(TextbookChapter).where(TextbookChapter.book_id==book.id))).scalar_one()
            if count:
                continue
            path = private_path(book.file_path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != book.sha256:
                raise ValueError('Original PDF hash changed')
            targets.append(dict(id=book.id, filename=book.original_filename, subject=book.subject, grade=book.grade,
                sha256=book.sha256, path=str(path)))
    await engine.dispose()
    if args.prepare_windows:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(prepare_windows, targets))
        return
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(recognize_book, book, args.front_only) for book in targets]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(dict(book=result['book']['filename'], chapters=len(result['chapters']),
                published=sum(c['is_published'] for c in result['chapters']), diagnostics=result['diagnostics']), ensure_ascii=False), flush=True)
    if args.apply:
        backup = backup_sqlite(OUTPUT)
        (OUTPUT/'database-backup.json').write_text(json.dumps(dict(path=backup)), encoding='utf-8')
        for result in results:
            await apply_result(result)
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--front-only', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--prepare-windows', action='store_true')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--books', type=int, nargs='*')
    args = parser.parse_args()
    if args.front_only and args.apply:
        parser.error('A partial OCR survey cannot be published')
    asyncio.run(main(args))
