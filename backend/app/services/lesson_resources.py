"""Read the materials actually referenced by a saved lesson, without model calls."""
import re

from app.services.lesson_content import clean_lesson_content, _heading, _label
from app.services.lesson_materials import ASSET_IMAGE


def lesson_material_references(content):
    """Keep every image occurrence and its surrounding teaching section."""
    images, pending = {}, []
    headings = []
    fenced = False
    lines = clean_lesson_content(content).splitlines()
    for index, line in enumerate(lines):
        if re.match(r'^\s*(```|~~~)', line):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = _heading(line)
        label = _label(line)
        if not heading and len(label) <= 60 and re.match(
            r'^(?:情境导入|课堂导入|导入|新授|探究|实验探究|合作探究|巩固练习|随堂练习|课堂小结|作业布置)', label
        ) and (line.strip().startswith('**') or re.match(r'^\s*[（(]?[一二三四五六七八九十\d]+[）)、.]', line)):
            heading = (3, label)
        if heading:
            depth, title = heading
            headings = [(level, text) for level, text in headings if level < depth]
            headings.append((depth, title))
        section = ' / '.join(title for _, title in headings) or '教案正文'
        for match in ASSET_IMAGE.finditer(line):
            identifier = match.group(2)
            # The surrounding text explains usage; the image itself is rendered separately.
            excerpt = ASSET_IMAGE.sub('', line).strip(' |')
            if not excerpt:
                adjacent = lines[max(0, index - 1):index] + lines[index + 1:index + 2]
                excerpt = ' '.join(text.strip() for text in adjacent
                                   if text.strip() and not _heading(text) and not ASSET_IMAGE.search(text))
            images.setdefault(identifier, []).append({
                'section': section, 'caption': match.group(1), 'excerpt': excerpt[:600],
            })
        # Only explicit placeholders become a to-do. Do not invent a URL or resource.
        for sentence in re.split(r'[。；\n]', line):
            if re.search(r'(?:图片|视频)(?:待插入|待补充|待查找)|(?:自行|需要|请)(?:查找|寻找|补充).{0,25}(?:图片|视频)', sentence):
                text = re.sub(r'^[\s|>*#\-]+', '', sentence).strip(' |')[:600]
                item = {'kind': 'video' if '视频' in text else 'image', 'section': section, 'description': text}
                if item not in pending:
                    pending.append(item)
    return images, pending
