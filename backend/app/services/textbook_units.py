"""Recover directory groups without changing reviewed lesson IDs or page ranges."""
import re
from collections import Counter
from functools import lru_cache

import fitz

from app.services.textbook_outline import contents_entries, page_lines, reviewed_directory
from app.services.textbook_service import private_path


UNIT = re.compile(r'^(?:第\s*[\d一二三四五六七八九十百零〇]+\s*单\s*元|(?:Starter\s+)?(?:Unit|Module)\s*\d+\b)', re.I)
APPENDIX = re.compile(r'^(?:附录|识字表|写字表|词语表|笔画名称表|常用偏旁名称表)')


def unit_title(text):
    text = re.sub(r'\s+', ' ', text).strip()
    match = UNIT.match(text)
    if not match:
        return ''
    # English lesson rows sometimes repeat their parent unit before a separator.
    if re.match(r'(?:Starter\s+)?(?:Unit|Module)', text, re.I) and re.search(r'\s+[·|]\s+', text):
        return ''
    marker = re.sub(r'\s+', '', match[0]) if text.startswith('第') else match[0]
    return marker + text[match.end():]


def unit_key(title):
    return re.sub(r'[\s.]+', '', UNIT.match(title)[0]).lower()


def directory_units(lines, width, height):
    """Pair unit headings (including headings without pages) with their first row."""
    markers = [line for line in lines if unit_title(line['text'])]
    if not markers:
        return []
    # Read independent contents columns from top to bottom, then left to right.
    if any(line['x'] > width * .46 for line in markers) and any(line['x'] < width * .46 for line in markers):
        left = [line for line in lines if line['x'] < width * .46]
        right = [{**line, 'x': line['x']-width*.46, 'right': line['right']-width*.46}
                 for line in lines if line['x'] >= width * .46]
        return directory_units(left, width*.46, height) + directory_units(right, width*.54, height)
    ordered = sorted(lines, key=lambda line: (line['y'], line['x']))
    positions = [index for index, line in enumerate(ordered) if unit_title(line['text'])]
    result = []
    for index, position in enumerate(positions):
        end = positions[index+1] if index+1 < len(positions) else len(ordered)
        chunk = ordered[position:end]
        entries = contents_entries(chunk, width, height)
        if not entries:
            continue
        title = unit_title(chunk[0]['text'])
        title = re.sub(r'[.．·…]{2,}\s*\d+\s*$', '', title).strip()
        # A separate theme under a bare unit marker belongs to its heading.
        if UNIT.fullmatch(title):
            for line in chunk[1:]:
                theme = line['text'].strip()
                if re.fullmatch(r'\d+|[.·…\s]+', theme):
                    continue
                if (not re.match(r'^(?:\d|第.+课|阅读|写作|习作|口语|任务|◎|●|Unit|Lesson|Section)', theme, re.I)
                        and not re.search(r'[.·…]{2,}|\d+\s*$', theme)):
                    title += ' ' + theme
                break
        result.append(dict(title=title, printed=min(entry['printed'] for entry in entries)))
    return result


@lru_cache(maxsize=160)
def source_units(path, modified, digest):
    review = reviewed_directory(digest)
    units = []
    if review:
        units = [dict(title=unit_title(entry['title']), printed=entry['printed'])
                 for entry in review['entries'] if unit_title(entry['title'])]
        # Hash-bound reviewed boundaries take precedence over native readings.
        # A contents footer must never move a later unit back to page one.
        if units:
            return units
    try:
        with fitz.open(path) as document:
            pages = review['contents_pages'] if review else range(1, min(22, len(document))+1)
            for number in pages:
                page = document[number-1]
                lines = page_lines(page)
                if (review or re.search(r'目\s*录|contents', page.get_text(), re.I)
                        or len(contents_entries(lines, page.rect.width, page.rect.height)) >= 6):
                    units.extend(directory_units(lines, page.rect.width, page.rect.height))
    except (OSError, RuntimeError, ValueError):
        # Missing/scanned PDFs still retain audited headings and explicit parents.
        pass
    return units


def group_chapter_directory(book, chapters):
    """Return display metadata; persisted chapter data stays untouched."""
    from app.services.textbook_catalog import is_removed_chapter
    chapters = [chapter for chapter in chapters if not is_removed_chapter(getattr(book, 'subject', ''), chapter['title'], getattr(book, 'grade', ''), getattr(book, 'sha256', ''))]
    if getattr(book, 'subject', '') == '英语' and getattr(book, 'grade', '').startswith('小学'):
        from app.services.textbook_primary_english import primary_english_directory
        directory = primary_english_directory(book, chapters)
        if directory is not None:
            return directory
    if getattr(book, 'subject', '') == '英语' and getattr(book, 'grade', '').startswith('初中'):
        from app.services.textbook_junior_english import junior_english_directory
        directory = junior_english_directory(book, chapters)
        if directory is not None:
            return directory
    from app.services.textbook_english import is_highschool_english, highschool_english_directory
    if is_highschool_english(book):
        directory = highschool_english_directory(book, chapters)
        if directory is not None:
            return directory
    if getattr(book, 'subject', '') == '地理':
        from app.services.textbook_geography import geography_directory
        return geography_directory(book, chapters)
    from app.services.textbook_biology import is_junior_biology, junior_biology_directory, is_highschool_biology, highschool_biology_directory
    if is_junior_biology(book):
        return junior_biology_directory(book, chapters)
    if is_highschool_biology(book):
        return highschool_biology_directory(book, chapters)
    from app.services.textbook_chemistry import is_highschool_chemistry, highschool_chemistry_directory
    if is_highschool_chemistry(book):
        return highschool_chemistry_directory(book, chapters)
    from app.services.textbook_physics import is_junior_physics, physics_directory, is_highschool_physics, highschool_physics_directory
    if is_highschool_physics(book) and not any(unit_title(chapter['title']) for chapter in chapters):
        return highschool_physics_directory(chapters)
    if is_junior_physics(book):
        return physics_directory(chapters)
    if getattr(book, 'subject', '') == '数学':
        from app.services.textbook_math import group_math_directory
        return group_math_directory(book, chapters)
    review = reviewed_directory(book.sha256)
    offsets = Counter()
    for chapter in chapters:
        printed = re.match(r'\s*(\d+)', chapter['printed_pages'])
        if printed:
            offsets[chapter['start_page']-int(printed[1])] += 1
    offset = review['offset'] if review else offsets.most_common(1)[0][0] if offsets else None
    path = private_path(book.file_path)
    source = source_units(str(path), path.stat().st_mtime_ns if path.is_file() else 0, book.sha256)
    units = {}
    if offset is not None:
        for entry in source:
            start = entry['printed']+offset
            key = unit_key(entry['title'])
            previous = units.get(key)
            # The first lesson can be later than the unit's decorative cover.
            units[key] = (min(start, previous[0]) if previous else start,
                          max((previous[1], entry['title']), key=len) if previous else entry['title'])
    for chapter in chapters:
        title = unit_title(chapter['title'])
        start = chapter['start_page']
        if title and unit_key(title) not in units:
            units[unit_key(title)] = (start, title)
    boundaries = dict(units.values())
    for chapter in chapters:
        if APPENDIX.match(re.sub(r'^\d+\.\s*', '', chapter['title'])):
            boundaries[chapter['start_page']] = ''
    ordered = sorted(boundaries.items())
    result = []
    for chapter in chapters:
        title = chapter['parent_title']
        for start, heading in ordered:
            if start > chapter['start_page']:
                break
            title = heading
        result.append({**chapter, 'unit_title': title, 'is_unit': bool(unit_title(chapter['title']))})
    if getattr(book, 'subject', '') == '政治' and getattr(book, 'grade', '').startswith('高中'):
        from app.services.textbook_politics import politics_chapter_hierarchy
        result = politics_chapter_hierarchy(result)
    return result
