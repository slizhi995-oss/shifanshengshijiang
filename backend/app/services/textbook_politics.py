"""Preserve the unit / lesson / topic hierarchy printed in politics books."""
import re


LESSON = re.compile(r'^第\s*[\d一二三四五六七八九十百零〇]+\s*课')
UNIT = re.compile(r'^第\s*[\d一二三四五六七八九十百零〇]+\s*单\s*元')
INQUIRY = re.compile(r'^综合探究')


def politics_chapter_hierarchy(chapters, pages=None):
    """Keep inquiries at unit level and include every topic in a full lesson.

    Pages are optional: rendering only adds parent/indent metadata; extraction
    and the repair script also rebuild complete lesson content from source pages.
    Input order is the reviewed directory order, including same-page headings.
    """
    result, lesson = [], ''
    for index, chapter in enumerate(chapters):
        title = chapter['title'].strip()
        heading = bool(LESSON.match(title))
        boundary = bool(UNIT.match(title) or INQUIRY.match(title))
        if boundary:
            lesson = ''
        row = {**chapter, 'parent_title': lesson if not heading else ''}
        if pages is None:
            row['is_nested'] = bool(lesson) and not heading
        if heading:
            lesson = chapter['title']
            if pages is not None:
                next_page = next((other['start_page'] for other in chapters[index+1:]
                                  if LESSON.match(other['title']) or UNIT.match(other['title'])
                                  or INQUIRY.match(other['title'])), len(pages)+1)
                row['end_page'] = next_page-1
                row['content'] = '\n\n'.join(f'[PDF第{number}页]\n{pages[number-1]}'
                                            for number in range(row['start_page'], row['end_page']+1))
        result.append(row)
    return result
