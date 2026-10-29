"""Derive chapter ranges from PDF contents and corroborating body headings.

No model calls or OCR. Uncorroborated entries remain drafts. Page numbers in
the printed contents are resolved using body footers and matching headings,
never by assuming that PDF page numbers equal printed numbers.
"""
import re
import unicodedata
import json
from pathlib import Path
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import fitz

from app.services.textbook_service import clean_page
from app.services.textbook_catalog import clean_chapter_title, numbered_chapter_title, has_chapter_number, is_removed_chapter


def reviewed_directory(sha256):
    """Use the audited directory only for the exact original PDF digest."""
    path=Path(__file__).resolve().parents[1]/'data'/'textbook_directories.json'
    return json.loads(path.read_text(encoding='utf-8')).get(sha256) if path.exists() else None


def compact(text):
    text = unicodedata.normalize('NFKC', text)
    return re.sub(r'[^\w\u4e00-\u9fff]', '', text).lower()


def title_key(title):
    title = unicodedata.normalize('NFKC', title)
    original = title
    title = re.sub(r'^第\s*([\d一二三四五六七八九十百]+)\s*([章节课单元]+)',r'第\1\2',title)
    title = re.split(r'[/／]', title)[0]
    for _ in range(2):
        title = re.sub(r'^[◎○\s]*(?:阅读|课文)\s*(?=\d)', '', title)
        title = re.sub(r'^(?:第[\d一二三四五六七八九十百]+[章节课单元]+|[\d.、*\s]+|(?:starter\s+)?unit\s*\d+)', '', title, flags=re.I)
    title = re.sub(r'^(?:阅读与思考|探究与发现|信息技术应用|文献阅读与数学写作|口语交际|习作例文|习作)[\s:：\ue012]*', '', title.strip())
    return compact(title) or compact(original)


def reconcile_directory_entries(reviewed, native):
    """Use printed directory labels, including detached numbers and symbols."""
    labels = {}
    for entry in native:
        labels.setdefault((entry['printed'], title_key(entry['title'])), []).append(entry['title'])
    result = []
    for entry in reviewed:
        candidates = labels.get((entry['printed'], title_key(entry['title'])), [])
        candidates = [title for title in candidates if title.count('*') == entry['title'].count('*')]
        # Conflicting readings require review; don't pick a guessed sequence.
        title = candidates[0] if len(set(candidates)) == 1 else entry['title']
        result.append({**entry, 'title': numbered_chapter_title(title, 0)})
    return result


def heading_matches(title, text):
    key = title_key(title)
    body = compact(text)
    if len(key) < 2:
        return bool(key) and any(compact(line) in (key, compact(title)) for line in text.splitlines())
    if key in body:
        return True
    chinese_key = ''.join(re.findall(r'[\u4e00-\u9fff]', key))
    if len(chinese_key) >= 2 and len(chinese_key) == len(key):
        # Lower-primary reading titles can have pinyin inserted between each
        # Chinese glyph in extraction order. Corroborate their Chinese text.
        chinese_body = ''.join(re.findall(r'[\u4e00-\u9fff]', body))
        if chinese_key in chinese_body:
            return True
    # Long multi-line titles can contain PDF ligatures or missing glyphs.
    match = SequenceMatcher(None, key, body, autojunk=False).find_longest_match()
    return len(key) >= 8 and match.size >= max(7, len(key) * .8)


def page_lines(page):
    lines = []
    for block in page.get_text('dict', flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']:
        for line in block.get('lines', []):
            # Some PDFs put the next title and previous leader/page number in
            # one MuPDF "line". Split those spans by their actual baselines.
            spans = line['spans']
            groups = []
            if max(s['origin'][1] for s in spans)-min(s['origin'][1] for s in spans) > 12:
                for span in sorted(spans, key=lambda s: s['origin'][1]):
                    group = next((g for g in groups if abs(g[0]['origin'][1]-span['origin'][1]) < 6), None)
                    if group is None:
                        groups.append([span])
                    else:
                        group.append(span)
            else:
                groups = [spans]
            for group in groups:
                group.sort(key=lambda span: span['bbox'][0])
                text = unicodedata.normalize('NFKC', ''.join(span['text'] for span in group)).strip().replace('\ue010', '.')
                if not text or re.search(r'仅供个人|未经授权|公众号|微信|www\.', text):
                    continue
                x0 = min(s['bbox'][0] for s in group); x1 = max(s['bbox'][2] for s in group)
                y0 = min(s['bbox'][1] for s in group); y1 = max(s['bbox'][3] for s in group)
                lines.append(dict(text=text, x=x0, right=x1, y=(y0+y1)/2,
                                  top=y0, size=max(span['size'] for span in group)))
    return sorted(lines, key=lambda line: (line['y'], line['x']))


def contents_entries(lines, width, height):
    """Pair right-column page numbers with titles at the same baseline."""
    lines = [line for line in lines if line.get('size',12)>=7]
    slash_entries = []
    for line in lines:
        match = re.match(r'^(.+?)\s*[/／]\s*(\d{1,3})\s*$', line['text'])
        if match and line['y'] < height*.94 and len(title_key(match.group(1))) >= 1:
            title = match.group(1).strip()
            # Chapter numbers sit above their names in a separate left column.
            # Join by position so the adjacent lesson column cannot be included.
            markers = [marker for marker in lines
                       if re.fullmatch(r'第\s*[\d一二三四五六七八九十百零〇]+\s*章', marker['text'])
                       and 0 < line['y']-marker['y'] < 45 and abs(marker['x']-line['x']) < 20]
            if markers and not re.match(r'^第.+[章节]', title):
                title = re.sub(r'\s+', '', max(markers, key=lambda item: item['y'])['text']) + ' ' + title
            slash_entries.append(dict(title=title, printed=int(match.group(2))))
    # Some editions print chapter names in a large left column and lessons in
    # a separate right column, each explicitly followed by “/ page”.
    if len(slash_entries) >= 4:
        return sorted(slash_entries, key=lambda entry: entry['printed'])
    # Elementary Chinese books have two independent contents columns.
    left = [line for line in lines if line['x'] < width*.46 and line['right'] < width*.55]
    # The gutter is often just left of the geometric page centre. Requiring
    # x > 50% loses the entire second column in several primary editions.
    right = [line for line in lines if line['x'] > width*.46]
    leaders = lambda group: sum(bool(re.search(r'[.·…]{2,}\s*\d+\s*[.．·…]*\s*$', line['text'])) for line in group)
    if leaders(left) >= 3 and leaders(right) >= 3:
        shifted = [{**line, 'x': line['x']-width*.46, 'right': line['right']-width*.46} for line in right]
        return contents_entries(left, width*.5, height) + contents_entries(shifted, width*.54, height)
    rows = []
    for line in lines:
        if line['y'] > height * .96:
            continue
        row = next((row for row in reversed(rows[-3:]) if abs(row[0]['y'] - line['y']) <
                    (6 if re.fullmatch(r'\d{1,3}',line['text']) or all(re.fullmatch(r'\d{1,3}',item['text']) for item in row) else 3)), None)
        if row is None:
            rows.append([line])
        else:
            row.append(line)
    entries, pending = [], ''
    for row in rows:
        row.sort(key=lambda line: line['x'])
        stars = ''.join(line['text'] for line in row if re.fullmatch(r'\*+',line['text']))
        text = ' '.join(line['text'] for line in row if not re.fullmatch(r'\*+',line['text']))
        if stars and '*' not in text:
            text = re.sub(r'^(\s*\d+)\s*',lambda m:m[1]+stars+' ',text) if re.match(r'^\s*\d+',text) else stars+' '+text
        if compact(text) in ('目录', 'contents', 'content'):
            pending = ''; continue
        right_number = next((line for line in reversed(row) if re.fullmatch(r'\d{1,3}', line['text']) and line['x'] > width * .45), None)
        if right_number is None and re.search(r'第[\d一二三四五六七八九十]+单元', text):
            right_number = next((line for line in row if re.fullmatch(r'\d{1,3}', line['text'])),None)
        if right_number:
            # A separate left-hand number is the lesson number, not noise.
            title = ' '.join(line['text'] for line in row if line is not right_number and not re.fullmatch(r'\*+', line['text']))
            if stars and '*' not in title:
                title = re.sub(r'^(\s*\d+)\s*',lambda m:m[1]+stars+' ',title) if re.match(r'^\s*\d+',title) else stars+' '+title
            number = int(right_number['text'])
        else:
            match = re.match(r'^(.*?[^\d\s])[\s.…·_—-]*(\d{1,3})\s*[.．·…]*\s*$', text)
            if not match or not any(line['right'] > width*.65 for line in row):
                # Chapters and wrapped titles are joined with the following row.
                continuation = re.match(r'^(?:第.+(?:单元|章)|综合与实践|阅读与思考|\d+\s*\D)', pending)
                new_heading = re.match(r'^(?:第.+(?:单元|章|课)|\d+\s*[* .、]|写作|习作|口语交际|◎)', text)
                pending = (pending + ' ' + text if continuation and not new_heading else text) if len(text) < 110 else ''
                continue
            title, number = match.group(1), int(match.group(2))
        title = re.sub(r'[.…·_]{2,}', '', title).strip().rstrip('/').strip()
        if re.fullmatch(r'[.．·…_]*', title):
            title = ''
        title = clean_chapter_title(title)
        # Text labels embedded inside the directory's decorative illustrations
        # must not become part of an adjacent lesson heading.
        marker = re.search(r'(?:第[\d一二三四五六七八九十]+[章节]|整理与提升)',title)
        if marker and marker.start()>0 and not re.search(r'[\u4e00-\u9fff]',title[:marker.start()]):
            title=title[marker.start():]
        if pending and not re.match(r'^(?:第[\d一二三四五六七八九十]+|\d+\s*[* .、]|[一二三四五六七八九十]+[、 ])', title):
            # A preceding poem without a printed page is a sub-entry, not a
            # continuation of the next writing/practice heading.
            prefix = re.match(r'^[◎●.\s]*(?:口语交际|习作|综合性学习|综合与实践|跨学科|附录|实验活动|问题研究|科技探索|拓展视野|生物科技|科学|图说数学史|探究|阅读与思考|信息技术应用|文献阅读|综合探究|第.+(?:课|单元|章)|\d+\s*\*?\s*\D|电解质)',pending)
            if prefix:
                title = (clean_chapter_title(pending) + ' ' + title).strip()
        pending = ''
        if compact(title) in ('目录', 'contents', 'content'):
            continue
        if 1 <= number and 1 <= len(title_key(title)) <= 150:
            entries.append(dict(title=title[:160], printed=number))
    return entries


def english_entries(lines, width, height):
    """English contents tables: only use the Units column, not grammar columns."""
    # Newer editions combine “UNIT 1” in one text box and place “p. 1”
    # beside a multi-line theme below it. Keep the entire theme row together.
    markers = [(line, re.fullmatch(r'unit\s*(\d+)', line['text'], re.I))
               for line in lines if line['x'] < width*.34]
    markers = [(line, match) for line, match in markers if match]
    if len(markers) >= 3:
        entries = []
        for index, (marker, match) in enumerate(markers):
            bottom = markers[index+1][0]['top']-3 if index+1<len(markers) else height*.83
            row = [line for line in lines if marker['y'] < line['y'] < bottom]
            number = next((re.fullmatch(r'p\.?\s*(\d+)', line['text'], re.I)
                           for line in row if line['x'] < marker['x']-5
                           and re.fullmatch(r'p\.?\s*(\d+)', line['text'], re.I)), None)
            themes = [line for line in row if line['x'] >= marker['x']-3 and line['right'] < width*.36
                      and not re.fullmatch(r'workbook|appendices',line['text'],re.I)]
            if number and themes:
                title = f'Unit {match.group(1)} ' + ' '.join(line['text'] for line in themes)
                entries.append(dict(title=title[:160], printed=int(number.group(1))))
        if entries:
            return entries
    page_anchors = [line for line in lines if re.fullmatch(r'(?:p\.?|page)\s*\d+', line['text'], re.I) and line['x'] < width*.38]
    entries, previous_y = [], 0
    for anchor in page_anchors:
        column = [line for line in lines if previous_y < line['y'] < anchor['y'] and line['x'] < width*.34
                  and line['right'] < width*.36 and line['y'] < height*.94]
        markers = [line for line in column if re.fullmatch(r'[\d➊➋➌➍➎➏➐➑➒➓]+', line['text'])]
        if markers:
            marker = markers[-1]
            title_lines = [line for line in column if line['y'] >= marker['y']-5 and line is not marker
                           and not re.fullmatch(r'(?:starter\s+)?units?|contents', line['text'], re.I)]
            if title_lines:
                max_size = max(line['size'] for line in title_lines)
                title_lines = [line for line in title_lines if line['size'] >= max_size*.94]
                labels = [line for line in lines if line['y'] <= marker['y'] and line['x'] < width*.34
                          and re.fullmatch(r'(?:starter\s+)?units?',line['text'],re.I)]
                label = 'Starter Unit' if labels and re.search('starter',labels[-1]['text'],re.I) else 'Unit'
                number = marker['text'].translate(str.maketrans('➊➋➌➍➎➏➐➑➒➓', '1234567890'))
                title = f'{label} {number} ' + ' '.join(line['text'] for line in title_lines)
                entries.append(dict(title=title[:160], printed=int(re.search(r'\d+', anchor['text']).group())))
        previous_y = anchor['y']
    return entries


def extract_outline(document, subject, reviewed_contents=None, reviewed_toc_pages=None, reviewed_offset=None, *, grade=''):
    texts = [clean_page(page.get_text(sort=True)) for page in document]
    headers = []
    footer_offsets = Counter()
    footer_pages = defaultdict(list)
    front = {}
    for index, page in enumerate(document, 1):
        # Only the upper portion corroborates chapter headings; a passing
        # mention in an exercise must not establish a chapter boundary.
        headers.append(page.get_text(clip=(0, 0, page.rect.width, page.rect.height*.48), sort=True))
        for line in page.get_text().splitlines()[-12:]:
            if re.fullmatch(r'\s*\d{1,3}\s*', line):
                number = int(line)
                if 0 <= index-number <= 30:
                    footer_offsets[index-number] += 1
                    footer_pages[number].append(index)
        if index <= min(22, len(document)):
            front[index] = page_lines(page)
    contents, toc_pages = [], []
    active_until = 0
    for index, lines in front.items():
        page = document[index-1]
        has_heading = any(compact(line['text']) in ('目录', 'contents', 'content') for line in lines)
        entries = english_entries(lines, page.rect.width, page.rect.height) if subject == '英语' else []
        entries = entries or contents_entries(lines, page.rect.width, page.rect.height)
        continuation = index == toc_pages[-1]+1 if toc_pages and getattr(document, 'is_ocr', False) else index <= active_until
        heuristic = not getattr(document, 'is_ocr', False) and ((index <= 10 and len(entries) >= 6) or (subject == '英语' and len(entries) >= 2))
        if len(entries) >= 3 and (has_heading or continuation or heuristic):
            contents.extend(entries); toc_pages.append(index); active_until = index+2
    if reviewed_contents is not None:
        # Audited boundaries can predate a parser fix that recovered detached
        # lesson numbers. Restore those labels without changing the audit.
        contents = reconcile_directory_entries(reviewed_contents, contents)
        toc_pages = reviewed_toc_pages or toc_pages
    last_toc = max(toc_pages, default=2)
    # Drop non-monotone auxiliary indexes after the main contents.
    ordered, previous = [], 0
    source_contents=sorted(contents,key=lambda e:e['printed']) if reviewed_contents is not None else contents
    for entry in source_contents:
        if reviewed_contents is None and entry['printed'] < previous:
            continue
        if not ordered or (entry['printed'], compact(entry['title'])) != (ordered[-1]['printed'], compact(ordered[-1]['title'])):
            ordered.append(entry); previous = entry['printed']
    resolved = []
    offset_votes = Counter()
    for entry in ordered:
        matches = [i for i in range(last_toc+1, min(len(document), entry['printed']+30)+1)
                   if 0 <= i-entry['printed'] <= 30 and heading_matches(entry['title'], headers[i-1])]
        if matches:
            for i in matches:
                offset_votes[i-entry['printed']] += 1
    offsets = [reviewed_offset] if reviewed_offset is not None else [offset for offset, _ in (offset_votes or footer_offsets).most_common(6)]
    # A hash-bound, visually transcribed directory has explicit boundaries.
    # Validate its page offset using several body headings (including running
    # unit titles on the next page when a decorative cover defeats OCR).
    reviewed_anchors = 0
    if reviewed_contents is not None and reviewed_offset is not None:
        for entry in ordered:
            start = entry['printed']+reviewed_offset
            if last_toc < start <= len(document):
                body = '\n'.join(texts[start-1:min(start+1,len(document))])
                reviewed_anchors += heading_matches(entry['title'], body)
    trusted_directory = reviewed_anchors >= 3
    for entry in ordered:
        if trusted_directory:
            start = entry['printed']+reviewed_offset
            if last_toc < start <= len(document):
                resolved.append(dict(title=entry['title'],start_page=start,printed_pages=str(entry['printed']),verified=True))
            continue
        candidates = [entry['printed']+offset for offset in offsets]
        if reviewed_offset is None:
            candidates += footer_pages[entry['printed']]
        start = next((i for i in candidates if last_toc < i <= len(document) and heading_matches(entry['title'], headers[i-1])), None)
        if start:
            resolved.append(dict(title=entry['title'], start_page=start, printed_pages=str(entry['printed']), verified=True))
        elif offsets and offset_votes[offsets[0]] >= 3:
            # Preserve this boundary as a draft so adjacent published lessons
            # cannot silently absorb an unresolved contents entry.
            start = entry['printed'] + offsets[0]
            if last_toc < start <= len(document):
                resolved.append(dict(title=entry['title'], start_page=start, printed_pages=str(entry['printed']), verified=False))
    # Genuine PDF bookmarks are another source, provided the target heading
    # exists in the body. Ignore download-site/watermark bookmarks.
    for level, title, start in document.get_toc():
        if not last_toc < start <= len(document) or re.search(r'微信|公众号|教材电子|下载|目录|封面|扉页|使用说明', title):
            continue
        if heading_matches(title, headers[start-1]):
            resolved.append(dict(title=title[:160], start_page=start, printed_pages='', verified=True))
    # When a book has no machine-readable contents, use explicit chapter/lesson
    # headings at the top of body pages. Never turn numbered exercises into chapters.
    if len(resolved) < 3:
        for index, page in enumerate(document, 1):
            if index <= last_toc:
                continue
            for line in page_lines(page):
                text = line['text']
                if line['top'] > page.rect.height*.36 or line['size'] < 13:
                    continue
                if re.match(r'^(?:第[\d一二三四五六七八九十百]+[课章节单元]|\d{1,2}\.\d{1,2}\s*[^\d]|(?:Starter\s+)?(?:Unit|Module|Lesson)\s+\d+\b)', text, re.I) and len(title_key(text)) >= 2:
                    resolved.append(dict(title=text[:160], start_page=index, printed_pages='', verified=True))
                    break
    by_start = {}
    for entry in sorted(resolved, key=lambda item: (item['start_page'], not item['verified'])):
        # Chapter headings, lessons and poems can share their opening page.
        # Deduplicate the same title only, never every entry on that page.
        key = (entry['start_page'], title_key(entry['title']))
        by_start.setdefault(key, entry)
    entries = list(by_start.values())
    chapters = []
    for index, entry in enumerate(entries):
        next_start = next((item['start_page'] for item in entries[index+1:] if item['start_page'] > entry['start_page']), len(document)+1)
        end = next_start-1
        start = entry['start_page']
        if re.search(r'(?:诗[词歌]?|文言文|散文诗|寓言|短诗).*?[二三四五六七八九十\d]+(?:首|则|篇)',entry['title']):
            peers=[item for item in entries[index+1:] if item['start_page']>start and re.match(r'^(?:\d+\s*[* .、]|第.+单元|[◎○]|口语|习作|写作|综合|课外)',item['title'])]
            if peers:end=peers[0]['start_page']-1
        while sum(len(texts[number-1].strip()) for number in range(start,end+1))<40 and end<min(start+2,len(document)):
            end+=1
        content = '\n\n'.join(f'[PDF第{number}页]\n{texts[number-1]}' for number in range(start, end+1))
        text_length = sum(len(texts[number-1].strip()) for number in range(start, end+1))
        chapters.append(dict(title=numbered_chapter_title(entry['title'], index+1), parent_title='', start_page=start, end_page=end,
                             printed_pages=entry['printed_pages'], content=content,
                             is_published=entry['verified'] and 40 <= text_length and len(content) <= 48000))
    if subject == '化学' and grade.startswith('高中'):
        from app.services.textbook_chemistry import chemistry_chapter_hierarchy
        review = dict(entries=reviewed_contents, offset=reviewed_offset) if reviewed_contents is not None and reviewed_offset is not None else None
        chapters = chemistry_chapter_hierarchy(chapters, texts, review)
    chapters = [chapter for chapter in chapters if not is_removed_chapter(subject, chapter['title'], grade)]
    if subject == '政治' and grade.startswith('高中'):
        from app.services.textbook_politics import politics_chapter_hierarchy
        chapters = politics_chapter_hierarchy(chapters, texts)
    return texts, chapters, dict(contents_pages=toc_pages, candidates=len(ordered), matched=len(chapters),
                                offsets=offset_votes.most_common(4))
