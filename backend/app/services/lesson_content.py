"""Presentation rules shared by generation, historical previews and Word export."""
import re

PRESENTATION_RULES = '''
教案正文要求：
不输出“教材依据”“教材来源”“参考教材”等独立部分或来源页脚，教材关联信息由系统内部保存。
“教学准备”只列教具、设备、实验材料和课前任务；不列教材图号、图片清单、图注、图片说明或插图占位。
教材图片只在导入、新授、探究、练习等实际使用它的教学环节提出，说明教学用途；不要在教学准备重复。
标题层级、列表和教学过程表格保持清晰一致，不把整篇教案包在代码块中。表格中写文字，图片放在对应教学环节的独立段落。
'''

SOURCE = re.compile(r'^(?:教材依据|教材来源|参考教材|教材信息)(?:\s*$|\s*[：:（(]|及说明|与说明)')
PREPARATION = re.compile(r'^(?:教学准备|课前准备|教具准备)(?:\s*$|\s*[：:（(])')
MAJOR = re.compile(r'^(?:教学目标|教学重难点|教学重点|教学难点|教学准备|课前准备|教具准备|教学过程|教学环节|板书设计|作业|课后|教学反思|课堂小结|教材依据|教材来源|参考教材)')
FIGURE = re.compile(r'图\s*\d|教材(?:中|上|中的|上的)?(?:原图|配图|图片|插图|图示)|图片待(?:插入|补充)|\[\[图片')
IMAGE = re.compile(r'!\[[^\]\n]*\]\([^\n)]*\)|\[\[图片[：:][^\]\n]*\]\]')


def _label(text):
    text=text.replace('**','').replace('__','')
    text = re.sub(r'^[>\s#*◎⚠️]+|[*\s]+$', '', text).strip()
    return re.sub(r'^(?:[（(]?[一二三四五六七八九十\d]+[）)、.．:]\s*)+', '', text).strip()


def _heading(line):
    stripped=line.strip()
    match=re.match(r'^(#{1,6})\s+(.+?)\s*#*$',stripped)
    if match:return len(match.group(1)),_label(match.group(2))
    label=_label(stripped)
    if MAJOR.match(label) and (stripped.startswith('**') or re.match(r'^[（(]?[一二三四五六七八九十\d]+[）)、.．:]',stripped) or re.fullmatch(r'[^：:]+[：:]?',label)):
        return 2,label.rstrip('：:')
    return None


def _preparation_text(text):
    text=IMAGE.sub('',text)
    if FIGURE.match(re.sub(r'^[>\s*+\-]+','',text)):
        return ''
    # Keep useful equipment while removing parenthetical figure inventories.
    text=re.sub(r'[（(][^()（）\n]*(?:图\s*\d|教材.*(?:图片|插图|原图))[^()（）\n]*[）)]','',text)
    pieces=re.split(r'([，,；;])',text)
    kept=[]
    for index in range(0,len(pieces),2):
        piece=pieces[index]
        if not FIGURE.search(piece):
            kept.append(piece)
    return '，'.join(piece.strip(' ，,；;') for piece in kept if piece.strip(' ，,；;'))


def clean_lesson_content(content):
    """Hide source sections and preparation-only figure material, keeping teaching images."""
    content=content.replace('\r\n','\n').replace('\r','\n')
    wrapper=re.fullmatch(r'\s*```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*',content)
    if wrapper:content=wrapper.group(1)
    result=[];source_depth=None;preparation_depth=None;fence=None
    for line in content.split('\n'):
        marker=re.match(r'^\s*(?:>\s*)?(`{3,}|~{3,})',line)
        if marker:
            if fence is None:fence=marker.group(1)[0]
            elif marker.group(1)[0]==fence:fence=None
            if source_depth is None:result.append(line)
            continue
        heading=_heading(line) if fence is None else None
        if heading:
            depth,label=heading
            if source_depth is not None and depth<=source_depth:source_depth=None
            if preparation_depth is not None and depth<=preparation_depth:preparation_depth=None
            if SOURCE.match(label):source_depth=depth;continue
            if source_depth is not None:continue
            if PREPARATION.match(label):preparation_depth=depth
        if source_depth is not None:continue
        # Historical image insertion could leave the sentence terminator alone.
        if fence is None and re.fullmatch(r'[\s。；，、]+',line) and line.strip():continue
        if SOURCE.match(_label(line)):continue
        if line.lstrip().startswith('|'):
            cells=line.strip().strip('|').split('|')
            if cells and SOURCE.match(_label(cells[0])):continue
        if preparation_depth is not None and not heading:
            if re.fullmatch(r'(?:特别说明|图片说明|教材图片|图片要求|配图清单)[：:]?',_label(line)):continue
            if line.lstrip().startswith('|') and not re.fullmatch(r'[| :\-]+',line.strip()):
                cells=[_preparation_text(cell) for cell in line.strip().strip('|').split('|')]
                if not any(cell.strip() for cell in cells[1:]):continue
                line='| '+' | '.join(cells)+' |'
            elif FIGURE.search(line) or IMAGE.search(line):
                line=_preparation_text(line)
                if not re.sub(r'[>\s*\-\d.、]+','',line):continue
        result.append(line)
    return re.sub(r'\n{3,}','\n\n','\n'.join(result)).strip()
