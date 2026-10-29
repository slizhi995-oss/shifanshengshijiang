"""Reviewed high-school English contents: unit / selectable column.

The transcription is bound to the original PDF digest. Separate italic strategy
paragraphs and empty slash cells are deliberately absent. Each topic uses the
actual main-book or workbook pages, never the contents page itself. Topic
transcriptions remain available for auditing; imports persist merged columns.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from app.services.textbook_english_sections import expand_section_chapters, section_directory_from_review


SEPARATOR = ' · '


def is_highschool_english(book):
    return getattr(book, 'subject', '') == '英语' and getattr(book, 'grade', '').startswith('高中')


@lru_cache(maxsize=1)
def reviewed_english_directories():
    path = Path(__file__).resolve().parents[1]/'data'/'highschool_english_directories.json'
    return json.loads(path.read_text(encoding='utf8'))


def english_topic_chapters(digest, texts):
    """Build persisted topic rows using reviewed, one-based printed page ranges."""
    review = reviewed_english_directories().get(digest)
    return topic_chapters_from_review(review, texts)


def topic_chapters_from_review(review, texts):
    if not review:
        return []
    result = []
    for unit in review['units']:
        for section in unit['sections']:
            for item in section['items']:
                first, last = item['pages']
                start, end = first+review['offset'], last+review['offset']
                if not 1 <= start <= end <= len(texts):
                    raise ValueError(f'English topic outside source PDF: {item["title"]}')
                content = '\n\n'.join(f'[PDF第{page}页]\n{texts[page-1]}' for page in range(start, end+1))
                length = sum(len(texts[page-1].strip()) for page in range(start, end+1))
                result.append(dict(title=item['title'], parent_title=unit['title']+SEPARATOR+section['title'],
                    start_page=start, end_page=end, printed_pages=str(first) if first == last else f'{first}-{last}',
                    content=content, is_published=40 <= length and len(content) <= 48000))
    return result


def expand_english_chapters(digest, chapters, texts):
    return expand_section_chapters(reviewed_english_directories().get(digest), chapters, texts)


def _unit_key(title):
    if re.fullmatch(r'welcome\s+unit', title, re.I):
        return 'welcome'
    match = re.fullmatch(r'unit\s*(\d+)\b[^·]*', title, re.I)
    return match[1] if match else None


def highschool_english_directory(book, chapters):
    """Display each original column as a selectable chapter under its unit."""
    review = reviewed_english_directories().get(book.sha256)
    if not review:
        return None
    result = section_directory_from_review(review, chapters, _unit_key)
    # Workbook units form a separate group and remain selectable despite their
    # displayed "Unit N" labels. Keep persisted titles and source bindings intact.
    workbooks = []
    for row in chapters:
        match = re.fullmatch(r'workbook\s+unit\s*(\d+)', row['title'].strip(), re.I)
        if match:
            workbooks.append((int(match[1]), {**row, 'display_title': f'Unit {int(match[1])}',
                'unit_title': 'WORKBOOK', 'section_title': '', 'is_unit': False, 'is_nested': False}))
    result.extend(row for _, row in sorted(workbooks, key=lambda item: (item[0], item[1].get('id', 0))))
    return result
