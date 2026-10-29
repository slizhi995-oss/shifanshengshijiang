"""Display source biology directories as unit / chapter / section / column."""
import re


ORDINAL = r'[\d一二三四五六七八九十百零〇]+'
UNIT = re.compile(rf'^第\s*{ORDINAL}\s*单\s*元')
CHAPTER = re.compile(rf'^第\s*{ORDINAL}\s*章')
SECTION = re.compile(rf'^第\s*{ORDINAL}\s*节')
COLUMN = re.compile(r'^(?:科学[·•・]技术[·•・]社会|与生物学有关的职业|科学家的故事|[一二三四五六七八九十]+\s)')
HIGHSCHOOL_COLUMN = re.compile(r'^(?:探究\s*[·•・]\s*实践|生物科技进展|生物科学史话|科技探索之路|拓展视野|科学[·•・]技术[·•・]社会|与生物学有关的职业|科学家的故事|[一二三四五六七八九十]+\s)')
PROJECT = re.compile(r'^综合实践项目')
STANDALONE = re.compile(r'^(?:附录|学习还将继续)')


def is_junior_biology(book):
    return getattr(book, 'subject', '') == '生物' and getattr(book, 'grade', '').startswith('初中')


def is_highschool_biology(book):
    return getattr(book, 'subject', '') == '生物' and getattr(book, 'grade', '').startswith('高中')


def biology_directory_title(title):
    label = re.sub(r'\s+', ' ', title).strip()
    label = re.sub(r'[.．…]{2,}\s*\d+\s*$', '', label).strip()
    label = re.sub(rf'^(第\s*{ORDINAL}\s*(?:单\s*元|章|节))\s*[.．]?\s*',
                   lambda match: re.sub(r'\s+', '', match[1])+' ', label).strip()
    return re.sub(r'^科学\s*[·•・]\s*技术\s*[·•・]\s*社会\s*', '科学·技术·社会 ', label)


def junior_biology_directory(book, chapters):
    return biology_directory(book, chapters)


def highschool_biology_directory(book, chapters):
    return biology_directory(book, chapters, highschool=True)


def biology_directory(book, chapters, *, highschool=False):
    """Add display hierarchy without altering stored records or source material."""
    from app.services.textbook_outline import reviewed_directory, title_key
    review = reviewed_directory(book.sha256)
    order = {(entry['printed']+review['offset'], title_key(entry['title'])): index
             for index, entry in enumerate(review['entries'])} if review else {}
    def source_order(row):
        title = row['title']
        rank = 0 if UNIT.match(title) else 1 if CHAPTER.match(title) else 2 if SECTION.match(title) else 3
        return row['start_page'], order.get((row['start_page'], title_key(title)), len(order)), rank
    result, unit, chapter, section = [], '', '', ''
    for row in sorted(chapters, key=source_order):
        title = biology_directory_title(row['title'])
        nested = False
        if UNIT.match(title):
            unit, chapter, section = title, '', ''
            parent = ''
        elif CHAPTER.match(title):
            chapter, section = title, ''
            parent = unit
        elif SECTION.match(title):
            section = title
            parent = chapter or unit
        elif (HIGHSCHOOL_COLUMN if highschool else COLUMN).match(title):
            parent = section or chapter or unit
            nested = bool(section) if highschool else bool(section or chapter)
        elif PROJECT.match(title):
            chapter, section = '', ''
            parent = unit
        elif STANDALONE.match(title):
            unit, chapter, section = '', '', ''
            parent = ''
        else:
            parent = chapter or unit
        if highschool:
            title = re.sub(r'^探究\s*[·•・]\s*实践\s*', '探究·实践 ', title)
        result.append({**row, 'title': title, 'display_title': title, 'parent_title': parent,
                       'unit_title': unit, 'is_unit': bool(UNIT.match(title)), 'is_nested': nested})
    return result
