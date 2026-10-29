"""Remove leading directory dots from existing chapter labels; preserve * marks.

Run from backend: python -m scripts.clean_chapter_titles [--apply]
"""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from app.core.database import async_session_factory, engine
from app.models.textbook import TextbookChapter
from app.services.textbook_catalog import clean_chapter_title
from scripts.import_textbook_library import backup_sqlite


async def main(apply=False):
    output = Path('outputs/chapter-title-cleanup')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(applied=apply, changes=[])
    try:
        async with async_session_factory() as db:
            chapters = (await db.execute(select(TextbookChapter).order_by(TextbookChapter.id))).scalars().all()
            original_stars = {c.id: (c.title.count('*'), c.parent_title.count('*')) for c in chapters}
            for chapter in chapters:
                changes = {field: dict(before=getattr(chapter, field), after=clean_chapter_title(getattr(chapter, field)))
                    for field in ('title', 'parent_title') if getattr(chapter, field)!=clean_chapter_title(getattr(chapter, field))}
                if changes:
                    report['changes'].append(dict(id=chapter.id, book_id=chapter.book_id, fields=changes))
            if apply and report['changes']:
                report['database_backup'] = backup_sqlite(output)
                by_id = {chapter.id: chapter for chapter in chapters}
                for change in report['changes']:
                    for field, values in change['fields'].items():
                        setattr(by_id[change['id']], field, values['after'])
                assert all((c.title.count('*'),c.parent_title.count('*'))==original_stars[c.id] for c in chapters)
                await db.commit()
                report['star_marks_preserved'] = True
            report['chapters_changed'] = len(report['changes'])
            (output/('applied.json' if apply else 'preview.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({key:value for key,value in report.items() if key!='changes'},ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    asyncio.run(main(parser.parse_args().apply))
