"""Two-level English directories backed by real, deduplicated source pages."""
import re


def teaching_sections(unit, junior=False):
    return [section for section in unit['sections']
            if not junior or re.match(r'^Section [AB]:', section['title'])]


def english_section_pages(book, chapter):
    """Return the exact reviewed page set, or None for an ordinary chapter."""
    if book.subject != '英语' or not book.grade.startswith(('初中', '高中')):
        return None
    from app.services.textbook_english import reviewed_english_directories
    from app.services.textbook_junior_english import reviewed_junior_english_directories
    junior = book.grade.startswith('初中')
    review = (reviewed_junior_english_directories() if junior else reviewed_english_directories()).get(book.sha256)
    if review:
        for unit in review['units']:
            if chapter.parent_title == unit['title']:
                for section in teaching_sections(unit, junior):
                    if chapter.title == section['title']:
                        return sorted({page + review['offset'] for item in section['items']
                                       for page in range(item['pages'][0], item['pages'][1] + 1)})
    return None


def page_label(pages):
    """Represent gaps explicitly, e.g. 14-15, 18-19, 74 (not 14-74)."""
    runs = []
    for page in sorted(set(pages)):
        if runs and page == runs[-1][-1] + 1:
            runs[-1].append(page)
        else:
            runs.append([page])
    return ', '.join(str(run[0]) if len(run) == 1 else f'{run[0]}-{run[-1]}' for run in runs)


def section_chapters_from_review(review, texts, junior=False):
    if not review:
        return []
    result = []
    for unit in review['units']:
        for section in teaching_sections(unit, junior):
            printed = sorted({page for item in section['items']
                              for page in range(item['pages'][0], item['pages'][1] + 1)})
            if not printed:
                continue
            pages = [page + review['offset'] for page in printed]
            if not 1 <= pages[0] <= pages[-1] <= len(texts):
                raise ValueError(f'English section outside source PDF: {section["title"]}')
            content = '\n\n'.join(f'[PDF第{page}页]\n{texts[page-1]}' for page in pages)
            length = sum(len(texts[page-1].strip()) for page in pages)
            result.append(dict(title=section['title'], parent_title=unit['title'],
                start_page=pages[0], end_page=pages[-1], printed_pages=page_label(printed),
                content=content, is_published=40 <= length and len(content) <= 48000))
    return result


def expand_section_chapters(review, chapters, texts, junior=False):
    if not review:
        return chapters
    sections = section_chapters_from_review(review, texts, junior)
    keys = {(row['parent_title'], row['title']) for row in sections}
    task_parents = {unit['title'] + ' · ' + section['title']
                    for unit in review['units'] for section in unit['sections']}
    # Re-imports and cached parser results must not resurrect the old task rows.
    return [row for row in chapters if row.get('parent_title', '') not in task_parents
            and (row.get('parent_title', ''), row['title']) not in keys] + sections


def section_directory_from_review(review, chapters, unit_key, junior=False):
    result = []
    for unit in review['units']:
        heading = next((row for row in chapters if not row.get('parent_title')
                        and unit_key(row['title']) == unit_key(unit['title'])), None)
        if heading is not None:
            result.append({**heading, 'display_title': unit['title'], 'unit_title': unit['title'],
                'section_title': '', 'is_unit': True, 'is_nested': False, 'directory_layout': 'sections'})
        for section in teaching_sections(unit, junior):
            row = next((row for row in chapters if row.get('parent_title') == unit['title']
                        and row['title'] == section['title']), None)
            if row is not None:
                result.append({**row, 'display_title': section['title'], 'unit_title': unit['title'],
                    'section_title': '', 'is_unit': False, 'is_nested': False, 'directory_layout': 'sections'})
    return result
