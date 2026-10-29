"""Present audited geography chapters, lessons and study columns."""
import re

from app.services.textbook_outline import reviewed_directory, title_key

HEADING = re.compile(r'^第\s*[\d一二三四五六七八九十百零〇]+\s*(?:章|单\s*元)')
SECTION = re.compile(r'^第\s*[\d一二三四五六七八九十百零〇]+\s*节')


def geography_directory_title(title, *, junior=False):
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'[.．·…]{2,}\s*\d+\s*$', '', title).strip()
    if junior:
        title = re.sub(r'^【?\s*跨学科主题学习\s*】?\s*', '【跨学科主题学习】 ', title)
    return title


def geography_directory(book, chapters):
    review = reviewed_directory(book.sha256)
    entries = {(entry['printed'] + review['offset'], title_key(entry['title'])): (index, entry)
               for index, entry in enumerate(review['entries'])} if review else {}
    def source_entry(row):
        return entries.get((row['start_page'], title_key(row['title'])), (len(entries), {}))
    rows = sorted(chapters, key=lambda row: (row['start_page'], source_entry(row)[0],
                                            0 if HEADING.match(row['title']) else 1))
    result, group = [], ''
    for index, row in enumerate(rows):
        title = source_entry(row)[1].get('display_title', row['title'])
        title = geography_directory_title(title, junior=getattr(book, 'grade', '').startswith('初中'))
        heading = bool(HEADING.match(title))
        is_unit = False
        if heading:
            end = next((i for i in range(index + 1, len(rows)) if HEADING.match(rows[i]['title'])), len(rows))
            is_unit = '单元' in title.replace(' ', '') or any(SECTION.match(r['title']) for r in rows[index + 1:end])
            group = title if is_unit else ''
        result.append({**row, 'display_title': title, 'unit_title': group,
                       'parent_title': '' if heading else group, 'is_unit': is_unit, 'is_nested': False})
    return result
