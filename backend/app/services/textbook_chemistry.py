"""Main printed chapter/section/experiment directory for high-school chemistry."""
import re

from app.services.textbook_catalog import is_removed_chapter


CHAPTER = re.compile(r'^第\s*[\d一二三四五六七八九十百零〇]+\s*章(?:\s|$)')
COLUMN = re.compile(r'^(?:探究|方法导引|研究与实践|化学与职业)\s+')
DISPLAY_FIELDS = ('unit_title', 'is_unit', 'is_nested', 'display_title')


def is_highschool_chemistry(book):
    return getattr(book, 'subject', '') == '化学' and getattr(book, 'grade', '').startswith('高中')


def chemistry_heading_title(title):
    label = re.sub(r'\s+', ' ', title).strip()
    return label if CHAPTER.match(label) else ''


def chemistry_chapter_hierarchy(chapters, pages=None, review=None, *, display=False):
    """Keep only printed chapters, sections and experimental activities.

    Removed reviews and appendices still form boundaries, so regular topics
    cannot absorb their pages. No source page, ID or historical binding changes.
    """
    labels, ordering = {}, {}
    if review:
        for index, entry in enumerate(review['entries']):
            start = entry['printed']+review['offset']
            for title in (entry['title'], entry.get('legacy_title', entry['title'])):
                labels[(start, re.sub(r'\s+', '', title))] = entry['title']
            ordering[(start, entry['title'])] = index
    ordered = []
    for chapter in chapters:
        start = chapter['start_page']
        title = labels.get((start, re.sub(r'\s+', '', chapter['title'])), chapter['title'])
        ordered.append({**chapter, 'title': title})
    ordered.sort(key=lambda row: (row['start_page'], ordering.get((row['start_page'], row['title']), len(ordering))))
    boundaries = [row['start_page'] for row in ordered if not COLUMN.match(row['title'])]
    # The audit retains review/appendix boundaries even after cache filtering.
    if review:
        boundaries.extend(entry['printed']+review['offset'] for entry in review['entries']
                          if not COLUMN.match(entry['title'])
                          and is_removed_chapter('化学', entry['title'], '高中'))
    result, parent = [], ''
    for row in ordered:
        if is_removed_chapter('化学', row['title'], '高中'):
            continue
        heading = chemistry_heading_title(row['title'])
        if heading:
            parent = heading
        stored = {**row, 'parent_title': '' if heading else parent}
        if pages is not None:
            start = row['start_page']
            candidates = [number for number in boundaries if number > start]
            end = min(candidates, default=len(pages)+1)-1
            stored['end_page'] = end
            stored['content'] = '\n\n'.join(f'[PDF第{number}页]\n{pages[number-1]}' for number in range(start, end+1))
        if display:
            stored.update(unit_title=parent, is_unit=bool(heading), is_nested=False,
                          display_title=heading or row['title'])
        else:
            for field in DISPLAY_FIELDS:
                stored.pop(field, None)
        result.append(stored)
    return result


def highschool_chemistry_directory(book, chapters):
    from app.services.textbook_outline import reviewed_directory
    return chemistry_chapter_hierarchy(chapters, review=reviewed_directory(book.sha256), display=True)
