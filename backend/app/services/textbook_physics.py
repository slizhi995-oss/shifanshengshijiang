"""Chapter headings and nested lesson directories for school physics."""
import re


CHAPTER = re.compile(r'^第\s*[\d一二三四五六七八九十百零〇]+\s*章(?:\s|$)')
SECTION = re.compile(r'^[*＊]?\s*第\s*[\d一二三四五六七八九十百零〇]+\s*节(?:\s|$)')
CHAPTER_REVIEW = re.compile(r'^(?:复习与提高|整理与复习|章末复习|本章小结|复习题)')


def is_junior_physics(book):
    return getattr(book, 'subject', '') == '物理' and getattr(book, 'grade', '').startswith('初中')


def is_highschool_physics(book):
    return getattr(book, 'subject', '') == '物理' and getattr(book, 'grade', '').startswith('高中')


def physics_heading_title(title):
    title = re.sub(r'\s+', ' ', title).strip()
    marker = CHAPTER.match(title)
    if not marker or CHAPTER_REVIEW.match(title[marker.end():].strip()):
        return ''
    return re.sub(r'\s*[·•]\s*概述\s*$', '', title)


def highschool_physics_directory(chapters):
    from app.services.textbook_catalog import is_removed_chapter
    result, parent = [], ''
    has_headings = any(physics_heading_title(row['title']) for row in chapters)
    for chapter in chapters:
        if is_removed_chapter('物理', chapter['title'], '高中'):
            continue
        heading = physics_heading_title(chapter['title'])
        if heading:
            if chapter.get('is_published', True):
                parent = heading
        elif not parent:
            # A partial admin-created directory can contain only lessons.
            parent = physics_heading_title(chapter.get('parent_title', ''))
            if has_headings and not parent:
                continue
        label = chapter['title']
        if not heading and CHAPTER.match(label):
            label = label[CHAPTER.match(label).end():].strip()
        result.append({**chapter, 'title': heading or chapter['title'],
                       'display_title': heading or label, 'parent_title': '' if heading else parent,
                       'unit_title': parent or heading, 'is_unit': bool(heading),
                       'is_nested': bool(parent) and not heading})
    return result


def stored_physics_directory(book, chapters):
    if is_highschool_physics(book):
        chapters = highschool_physics_directory(chapters)
    elif is_junior_physics(book):
        chapters = physics_directory(chapters)
    return [{key: value for key, value in chapter.items()
             if key not in ('unit_title', 'is_unit', 'is_nested', 'display_title')} for chapter in chapters]


def physics_directory(chapters):
    """Indent sections and chapter reviews beneath the chapter heading."""
    parent = ''
    result = []
    for chapter in chapters:
        heading = bool(CHAPTER.match(chapter['title']))
        if heading and chapter.get('is_published', True):
            parent = chapter['title']
        elif chapter['title'].startswith('附录'):
            parent = ''
        result.append({**chapter, 'parent_title': '' if heading else parent,
                       'unit_title': parent, 'is_unit': heading,
                       'is_nested': bool(SECTION.match(chapter['title'])) or chapter['title'].strip() == '整理与复习'})
    return result
