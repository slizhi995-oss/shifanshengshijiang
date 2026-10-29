"""Primary English: reviewed flat units and source-bound lesson columns."""
import json
import re
from functools import lru_cache
from pathlib import Path


FLAT_PRIMARY_ENGLISH_DIGESTS = frozenset({
    # Refreshed grade 5–6 PDFs, reviewed on 2026-10-21.
    'b47ee47d590565e4d5644cdca3f5f7bebae09289833b54dcd865fb4bcf361c44',
    '300cc235eef8705807355496ae9f8b95a3718d4e947e9d2ffc9d52d45e8235db',
    'e2a5fdda9147dc91e0b7afc5bf451459d6eb84d96d858629efd31ba7bb583763',
    '125831084793f9df01f90b2fb7bcf2f0850b209daa74abbf74661e16b0c0ce27',
    '23e347d258a8bf80b6f8b813edff7ba6c6a9a74033dfcb424e78cb9a26b54017',
    '20d8721c3e613f007a1a2b6c7c5cb5ca5786e4a5b14e0bb0197c8017bf148499',
    '121e4bed4640c818a43be345029536b16a1ea26e300be0f1727a25ac1ecc182a',
    'dd7c53639a9e54dc36b552ec92dab0443536c4ea3c80842c3fa3dd7c2ef5ef1e',
    '0411b214adcca507dd9699d5872cf173a2c226a16e11655717f199b483f38d91',
})


@lru_cache(maxsize=16)
def reviewed_flat_primary_english_directory(digest):
    if digest not in FLAT_PRIMARY_ENGLISH_DIGESTS:
        return None
    from app.services.textbook_outline import reviewed_directory
    review = reviewed_directory(digest)
    return {**review, 'entries': [entry for entry in review['entries']
        if re.match(r'^(?:Unit\s+\d+\b|Fun Time(?:\s+\d+)?$)', entry['title'], re.I)]}


@lru_cache(maxsize=1)
def reviewed_primary_english_directories():
    path = Path(__file__).resolve().parents[1]/'data'/'primary_english_directories.json'
    return json.loads(path.read_text(encoding='utf8'))


def primary_english_chapter_allowed(digest, title):
    """Allow each reviewed edition's teaching entries, excluding supplements."""
    flat = reviewed_flat_primary_english_directory(digest)
    if flat:
        return any(title == entry['title'] for entry in flat['entries'])
    review = reviewed_primary_english_directories().get(digest)
    if not review:
        return None
    return any(title == unit['title'] or any(
        title == unit['title']+' · '+item['title'] for item in unit['items'])
        for unit in review['units'])


def primary_english_topic_chapters(digest, texts):
    review = reviewed_primary_english_directories().get(digest)
    if not review:
        return []
    result = []
    for unit in review['units']:
        for item in unit['items']:
            first, last = item['pages']
            start, end = first+review['offset'], last+review['offset']
            if not 1 <= start <= end <= len(texts):
                raise ValueError(f'Primary English topic outside source PDF: {item["title"]}')
            length = sum(len(texts[number-1].strip()) for number in range(start, end+1))
            content = '\n\n'.join(f'[PDF第{number}页]\n{texts[number-1]}' for number in range(start, end+1))
            result.append(dict(title=unit['title']+' · '+item['title'], parent_title=unit['title'], start_page=start, end_page=end,
                printed_pages=str(first) if first == last else f'{first}-{last}', content=content,
                is_published=40 <= length and len(content) <= 48000))
    return result


def expand_primary_english_chapters(digest, chapters, texts):
    chapters = [row for row in chapters if primary_english_chapter_allowed(digest, row['title']) is not False]
    keys = {(row.get('parent_title', ''), row['title'], row['start_page']) for row in chapters}
    return chapters + [row for row in primary_english_topic_chapters(digest, texts)
        if (row['parent_title'], row['title'], row['start_page']) not in keys]


def _unit_number(title):
    match = re.match(r'^unit\s*(\d+)\b', title, re.I)
    return int(match[1]) if match else None


def primary_english_directory(book, chapters):
    flat = reviewed_flat_primary_english_directory(book.sha256)
    if flat:
        order = {entry['title']: index for index, entry in enumerate(flat['entries'])}
        return [{**row, 'display_title': row['title'], 'unit_title': '', 'section_title': '',
            'is_unit': False, 'is_nested': False, 'directory_layout': 'flat'}
            for row in sorted(chapters, key=lambda row: order.get(row['title'], len(order)))
            if row['title'] in order]
    review = reviewed_primary_english_directories().get(book.sha256)
    if not review:
        return None
    remaining = list(chapters)
    result = []
    for unit in review['units']:
        heading = next((row for row in remaining if not row.get('parent_title')
            and _unit_number(row['title']) == _unit_number(unit['title'])), None)
        if heading is not None:
            result.append({**heading, 'display_title': unit['title'], 'unit_title': unit['title'],
                'section_title': '', 'is_unit': True, 'is_nested': False})
            remaining.remove(heading)
        labels = {unit['title']+' · '+item['title']: item['title'] for item in unit['items']}
        order = {unit['title']+' · '+item['title']: index for index, item in enumerate(unit['items'])}
        rows = [row for row in remaining if row.get('parent_title') == unit['title'] and row['title'] in order]
        for row in sorted(rows, key=lambda row: (order.get(row['title'], len(order)), row.get('id', 0))):
            result.append({**row, 'display_title': labels.get(row['title'], row['title']), 'unit_title': unit['title'],
                'section_title': '', 'is_unit': False, 'is_nested': False})
            remaining.remove(row)
    return result
