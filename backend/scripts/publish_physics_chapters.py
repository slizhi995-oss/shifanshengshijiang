"""Publish the verified contents of the supplied Physics Required Book 1 PDF.

Run from backend: python -m scripts.publish_physics_chapters
Only chapter metadata/text are updated; existing IDs and image reviews are kept.
"""
import asyncio
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.models.textbook import Textbook, TextbookChapter, TextbookPage
from app.services.textbook_service import private_path


SOURCE_SHA256 = 'b0a84622a6ddc13c693ace0c5f4c8e906d7343ce2da47aa5ff396d063b88052a'
# Printed page numbers, checked against the contents and each section's first page.
# The source PDF has five front-matter pages before printed page 1.
CONTENTS = [
    ('走进物理课堂之前', '致同学们', 1, 1, '致同学们'),
    ('走进物理课堂之前', '序言 物理学：研究物质及其运动规律的科学', 2, 9, '物理学：研究物质及其运动规律的科学'),
    ('第一章 运动的描述', '第一章 运动的描述 · 概述', 10, 10, '运动的描述'),
    ('第一章 运动的描述', '质点 参考系', 11, 14, '质点参考系'),
    ('第一章 运动的描述', '时间 位移', 15, 20, '时间位移'),
    ('第一章 运动的描述', '位置变化快慢的描述——速度', 21, 26, '位置变化快慢的描述——速度'),
    ('第一章 运动的描述', '速度变化快慢的描述——加速度', 27, 32, '速度变化快慢的描述——加速度'),
    ('第一章 运动的描述', '第一章 复习与提高', 33, 34, '复习与提高'),
    ('第二章 匀变速直线运动的研究', '第二章 匀变速直线运动的研究 · 概述', 35, 35, '匀变速直线运动的研究'),
    ('第二章 匀变速直线运动的研究', '实验：探究小车速度随时间变化的规律', 36, 38, '实验：探究小车速度随时间变化的规律'),
    ('第二章 匀变速直线运动的研究', '匀变速直线运动的速度与时间的关系', 39, 41, '匀变速直线运动的速度与时间的关系'),
    ('第二章 匀变速直线运动的研究', '匀变速直线运动的位移与时间的关系', 42, 46, '匀变速直线运动的位移与时间的关系'),
    ('第二章 匀变速直线运动的研究', '自由落体运动', 47, 53, '自由落体运动'),
    ('第二章 匀变速直线运动的研究', '第二章 复习与提高', 54, 55, '复习与提高'),
    ('第三章 相互作用——力', '第三章 相互作用——力 · 概述', 56, 56, '相互作用——力'),
    ('第三章 相互作用——力', '重力与弹力', 57, 62, '重力与弹力'),
    ('第三章 相互作用——力', '摩擦力', 63, 67, '摩擦力'),
    ('第三章 相互作用——力', '牛顿第三定律', 68, 71, '牛顿第三定律'),
    ('第三章 相互作用——力', '力的合成和分解', 72, 75, '力的合成和分解'),
    ('第三章 相互作用——力', '共点力的平衡', 76, 79, '共点力的平衡'),
    ('第三章 相互作用——力', '第三章 复习与提高', 80, 81, '复习与提高'),
    ('第四章 运动和力的关系', '第四章 运动和力的关系 · 概述', 82, 82, '运动和力的关系'),
    ('第四章 运动和力的关系', '牛顿第一定律', 83, 87, '牛顿第一定律'),
    ('第四章 运动和力的关系', '实验：探究加速度与力、质量的关系', 88, 93, '实验：探究加速度与力、质量的关系'),
    ('第四章 运动和力的关系', '牛顿第二定律', 94, 98, '牛顿第二定律'),
    ('第四章 运动和力的关系', '力学单位制', 99, 103, '力学单位制'),
    ('第四章 运动和力的关系', '牛顿运动定律的应用', 104, 108, '牛顿运动定律的应用'),
    ('第四章 运动和力的关系', '超重和失重', 109, 112, '超重和失重'),
    ('第四章 运动和力的关系', '第四章 复习与提高', 113, 115, '复习与提高'),
    ('学习资源', '课题研究', 116, 120, '课题研究'),
    ('学习资源', '学生实验', 121, 124, '学生实验'),
    ('学习资源', '索引', 125, 125, '索引'),
]


def compact(text):
    return re.sub(r'\s+', '', text)


def backup_sqlite():
    if engine.url.get_backend_name() != 'sqlite':
        raise ValueError('This local bootstrap requires a SQLite database')
    source = Path(engine.url.database).resolve()
    destination = Path('outputs/physics-chapters') / f'app-before-{datetime.now():%Y%m%d-%H%M%S-%f}.db'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as original, sqlite3.connect(destination) as backup:
        original.backup(backup)
    return str(destination.resolve())


async def main():
    try:
        async with async_session_factory() as db:
            book = (await db.execute(select(Textbook).where(Textbook.sha256 == SOURCE_SHA256))).scalar_one()
            if book.subject != '物理' or book.grade != '高中一年级':
                raise ValueError('Unexpected textbook subject/grade')
            if hashlib.sha256(private_path(book.file_path).read_bytes()).hexdigest() != SOURCE_SHA256:
                raise ValueError('The stored source PDF has changed')
            pages = {page.page_number: page for page in (await db.execute(
                select(TextbookPage).where(TextbookPage.book_id == book.id))).scalars()}
            existing = list((await db.execute(select(TextbookChapter).where(
                TextbookChapter.book_id == book.id))).scalars())
            prepared = []
            for parent, title, start, end, heading in CONTENTS:
                first, last = start + 5, end + 5
                if compact(heading) not in compact(pages[first].content[:800]):
                    raise ValueError(f'Section heading does not match PDF page {first}: {title}')
                content = '\n\n'.join(f'[PDF第{number}页]\n{pages[number].content}'
                                       for number in range(first, last + 1))
                if not 40 <= len(content) <= 48000:
                    raise ValueError(f'Invalid chapter content length: {title}')
                matches = [chapter for chapter in existing if chapter.start_page == first]
                if len(matches) > 1:
                    raise ValueError(f'Duplicate chapters on PDF page {first}')
                chapter = matches[0] if matches else TextbookChapter(book_id=book.id)
                if matches and (chapter.end_page != last or chapter.title != title):
                    raise ValueError(f'Existing chapter differs from the verified contents: {title}')
                prepared.append((chapter, parent, title, first, last, start, end, content))
            backup = backup_sqlite()
            for chapter, parent, title, first, last, start, end, content in prepared:
                chapter.title, chapter.parent_title = title, parent
                chapter.start_page, chapter.end_page = first, last
                chapter.printed_pages = str(start) if start == end else f'{start}–{end}'
                chapter.content, chapter.is_published = content, True
                db.add(chapter)
            book.is_published = True
            await db.commit()
            print(json.dumps({'book_id': book.id, 'published_chapters': len(prepared),
                              'new_chapters': len(prepared) - len(existing), 'backup': backup}, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
