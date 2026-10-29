"""Repair the reviewed politics required-two book, preserving chapter IDs.

Run from backend: python -m scripts.repair_politics_required_two [--apply]
"""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookPage
from app.services.textbook_outline import reviewed_directory, title_key
from app.services.textbook_politics import politics_chapter_hierarchy
from scripts.import_textbook_library import backup_sqlite


DIGEST = '303dc526d8ce8de16b6b81752f8f4030819eadca5b093284c74603bd1292f347'


async def main(apply=False):
    output = Path('outputs/politics-directory')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, changes=[])
    try:
        async with async_session_factory() as db:
            book = (await db.execute(select(Textbook).where(Textbook.sha256 == DIGEST))).scalar_one()
            review = reviewed_directory(DIGEST)
            order = {(entry['printed']+review['offset'], title_key(entry['title'])): i
                     for i, entry in enumerate(review['entries'])}
            chapters = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id))).scalars().all()
            chapters.sort(key=lambda c: order[(c.start_page, title_key(c.title))])
            assert len(chapters) == len(order)
            assert len({(c.start_page, title_key(c.title)) for c in chapters}) == len(order)
            pages = (await db.execute(select(TextbookPage).where(TextbookPage.book_id == book.id)
                                     .order_by(TextbookPage.page_number))).scalars().all()
            assert [page.page_number for page in pages] == list(range(1, book.page_count+1))
            fields = ('id', 'title', 'parent_title', 'start_page', 'end_page', 'content')
            raw = [{key: getattr(chapter, key) for key in fields} for chapter in chapters]
            repaired = politics_chapter_hierarchy(raw, [page.content for page in pages])
            for before, after in zip(raw, repaired):
                assert len(after['content']) <= 48000
                for field in ('parent_title', 'end_page', 'content'):
                    if before[field] != after[field]:
                        report['changes'].append(dict(id=before['id'], field=field,
                                                      before=before[field], after=after[field]))
            if apply and report['changes']:
                report['database_backup'] = backup_sqlite(output)
                (output/'recovery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
                by_id = {chapter.id: chapter for chapter in chapters}
                for change in report['changes']:
                    setattr(by_id[change['id']], change['field'], change['after'])
                await db.commit()
            target = 'applied.json' if apply and report['changes'] else 'preview.json'
            (output/target).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps(dict(applied=apply, book_id=book.id, changed_fields=len(report['changes']),
                                  database_backup=report.get('database_backup')), ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    asyncio.run(main(parser.parse_args().apply))
