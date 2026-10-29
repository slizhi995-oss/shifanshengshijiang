"""Restore reviewed high-school chemistry labels, parents and full section text.

Run from backend: python -m scripts.repair_highschool_chemistry [--apply]
Chapter IDs, source pages, images and historical lesson records are preserved.
"""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookPage
from app.services.textbook_catalog import is_removed_chapter
from app.services.textbook_chemistry import chemistry_chapter_hierarchy
from app.services.textbook_outline import reviewed_directory
from scripts.import_textbook_library import backup_sqlite


async def main(apply=False):
    output = Path('outputs/highschool-chemistry-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, books=[], changes=[])
    try:
        async with async_session_factory() as db:
            books = (await db.execute(select(Textbook).where(Textbook.subject == '化学',
                     Textbook.grade.startswith('高中')).order_by(Textbook.id))).scalars().all()
            by_id = {}
            for book in books:
                review = reviewed_directory(book.sha256)
                if not review:
                    raise ValueError(f'No reviewed directory for book {book.id}')
                chapters = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id)
                            .order_by(TextbookChapter.start_page, TextbookChapter.id))).scalars().all()
                pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book.id)
                         .order_by(TextbookPage.page_number))).scalars().all()
                assert [page.page_number for page in pages] == list(range(1, book.page_count+1))
                by_id.update({chapter.id: chapter for chapter in chapters})
                raw = [{column.name: getattr(chapter, column.name) for column in chapter.__table__.columns}
                       for chapter in chapters]
                normalized = chemistry_chapter_hierarchy(raw, [page.content for page in pages], review)
                kept = {row['id'] for row in normalized}
                for row in normalized:
                    assert 1 <= row['start_page'] <= row['end_page'] <= book.page_count
                    assert 40 <= len(row['content']) <= 48000, (book.id, row['title'], len(row['content']))
                    for field in ('title', 'parent_title', 'end_page', 'content'):
                        before = getattr(by_id[row['id']], field)
                        if before != row[field]:
                            report['changes'].append(dict(id=row['id'], field=field, before=before, after=row[field]))
                for chapter in chapters:
                    if chapter.id not in kept and chapter.is_published:
                        assert is_removed_chapter(book.subject, chapter.title, book.grade)
                        report['changes'].append(dict(id=chapter.id, field='is_published', before=True, after=False))
                report['books'].append(dict(id=book.id, retained=len(normalized), hidden=len(chapters)-len(kept)))
            if apply and report['changes']:
                report['database_backup'] = backup_sqlite(output)
                (output/'recovery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
                for change in report['changes']:
                    setattr(by_id[change['id']], change['field'], change['after'])
                await db.commit()
            target = 'applied.json' if apply and report['changes'] else 'preview.json'
            (output/target).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
            print(json.dumps(dict(applied=apply, books=report['books'], changed_fields=len(report['changes']),
                                  database_backup=report.get('database_backup')), ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
