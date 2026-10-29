"""Recover mathematics chapter groups from source headings without changing IDs."""
import re
import unicodedata
from functools import lru_cache

import fitz

from app.services.textbook_outline import contents_entries, page_lines, reviewed_directory, title_key
from app.services.textbook_service import private_path
from app.services.textbook_catalog import is_removed_math_chapter


CHAPTER = re.compile(r'^第\s*([\d一二三四五六七八九十百零〇两]+)\s*章\s*(.+)$')
SECTION = re.compile(r'^[\s*＊\ue012]*(\d+)[.．]\d+')
APPENDIX = re.compile(r'^(?:附录|附表|部分中英文词汇索引|中英文词汇索引|词汇索引|后记)')
COLUMN = re.compile(r'^((?:文献阅读与数学写作|阅读与思考|探究与发现|信息技术应用|图说数学史|观察与猜想|实验与探究|综合与实践|数学探究|数学建模)[*＊]?)[\s:：]*(.+)$')


def chapter_number(text):
    if text.isdecimal():
        return int(text)
    digits = dict(zip('零〇一二三四五六七八九两', (0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 2)))
    total = current = 0
    for char in text:
        if char in digits:
            current = digits[char]
        elif char in ('十', '百'):
            total += (current or 1) * (10 if char == '十' else 100)
            current = 0
        else:
            return None
    return total + current


def chapter_heading(text):
    text = unicodedata.normalize('NFKC', text).strip()
    text = re.sub(r'[.．·…]{2,}.*$', '', text).strip()
    text = re.sub(r'\s+\d+\s*$', '', text)
    match = CHAPTER.match(text)
    if not match:
        return None
    return chapter_number(match[1]), f'第{match[1]}章 {match[2].strip()}'


@lru_cache(maxsize=80)
def source_math_chapters(path, modified, digest):
    review = reviewed_directory(digest)
    headings = dict(filter(None, (chapter_heading(entry['title'])
                                 for entry in review['entries']))) if review else {}
    if headings:
        return headings
    # Several junior editions print chapter headings without page numbers.
    # Read their actual contents headings, rather than inventing titles from
    # the first numbered section or interpreting the PDF page as a chapter.
    try:
        with fitz.open(path) as document:
            pages = review['contents_pages'] if review else range(1, min(12, len(document)) + 1)
            for number in pages:
                page = document[number - 1]
                if not review and not re.search(r'目\s*录', page.get_text()):
                    continue
                for line in page_lines(page):
                    heading = chapter_heading(line['text'])
                    if heading:
                        headings.setdefault(*heading)
    except (OSError, RuntimeError, ValueError):
        pass
    return headings


def primary_directory_labels(lines, width, height):
    """Pair source ordinals with their row and represent activity icons as ☘."""
    ordinals = [line for line in lines if re.fullmatch(r'[一二三四五六七八九十]+', line['text'])
                and line['x'] < width * .25]
    labels = {}
    for entry in contents_entries(lines, width, height):
        key = title_key(entry['title'])
        title_line = next((line for line in lines if title_key(line['text']) == key
                           and line['x'] > width * .25 and not re.fullmatch(r'\d+', line['text'])), None)
        ordinal = next((line['text'] for line in ordinals if title_line
                        and line['right'] < title_line['x']
                        and abs(line['y'] - title_line['y']) <= max(line['size'], title_line['size']) * .85), '')
        marker = ordinal or ('☘' if ordinals else '')
        label = f"{marker} {entry['title']}" if marker else entry['title']
        labels[(entry['printed'], key)] = label
    return labels


@lru_cache(maxsize=40)
def source_primary_math_labels(path, modified, digest):
    review = reviewed_directory(digest)
    labels = {}
    try:
        with fitz.open(path) as document:
            pages = review['contents_pages'] if review else range(1, min(12, len(document)) + 1)
            for number in pages:
                page = document[number - 1]
                if not review and not re.search(r'目\s*录', page.get_text()):
                    continue
                labels.update(primary_directory_labels(page_lines(page), page.rect.width, page.rect.height))
    except (OSError, RuntimeError, ValueError):
        pass
    return labels


def group_math_directory(book, chapters):
    chapters = [chapter for chapter in chapters if not is_removed_math_chapter('数学', chapter['title'])]
    path = private_path(book.file_path)
    if getattr(book, 'grade', '').startswith('小学'):
        labels = source_primary_math_labels(str(path), path.stat().st_mtime_ns if path.is_file() else 0, book.sha256)
        result = []
        for chapter in chapters:
            printed = re.match(r'\s*(\d+)', chapter['printed_pages'])
            label = labels.get((int(printed[1]), title_key(chapter['title']))) if printed else None
            result.append({**chapter, 'display_title': label or chapter['title'], 'unit_title': '', 'is_unit': False})
        return result
    headings = dict(source_math_chapters(str(path), path.stat().st_mtime_ns if path.is_file() else 0, book.sha256))
    for chapter in chapters:
        heading = chapter_heading(chapter['title'])
        if heading:
            headings[heading[0]] = heading[1]
    current = ''
    result = []
    for chapter in chapters:
        title = unicodedata.normalize('NFKC', chapter['title']).strip()
        heading = chapter_heading(title)
        section = SECTION.match(title)
        if heading:
            current = headings[heading[0]]
        elif section:
            current = headings.get(int(section[1]), '')
        elif APPENDIX.match(title):
            current = ''
        item = {**chapter, 'unit_title': current, 'is_unit': bool(heading)}
        if getattr(book, 'grade', '').startswith('高中'):
            column = COLUMN.match(chapter['title'].replace('\ue012', '*').strip())
            if column:
                item.update(display_title=f'{column[1]}  {column[2].strip()}',
                            is_nested=not column[1].startswith('综合与实践'))
        result.append(item)
    return result
