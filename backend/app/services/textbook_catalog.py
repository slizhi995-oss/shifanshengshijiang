"""Textbook filename conventions and school-stage compatibility."""
import re
import unicodedata
from pathlib import Path

SUBJECTS = ('语文', '数学', '英语', '物理', '政治', '道德与法治', '化学', '生物', '地理', '历史')
STAGES = ('小学', '初中', '高中')
FILENAME = re.compile(r'^(小学|初中|高中)(道德与法治|语文|数学|英语|物理|政治|化学|生物|地理|历史)(.+)$')


def is_removed_math_chapter(subject, title):
    if subject != '数学':
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    return bool(re.fullmatch(r'(?:小结|数学活动|复习(?:参考)?题[\s\d一二三四五六七八九十百零〇]*|部分中英文词汇索引)[\s.·…]*', label))


def is_removed_physics_appendix(subject, title):
    if subject != '物理':
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    return bool(re.match(r'^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?附\s*录', label))


def is_removed_highschool_physics(subject, title, grade):
    if subject != '物理' or not grade.startswith('高中'):
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    label = re.sub(r'^[*＊\s]*(?:\d+[、.]?\s+)?', '', label)
    return bool(re.match(r'^(?:致同学|走进物理课堂之前|序言|前言|引言|编者的话|使用说明|目录|'
                         r'课题研究|学生实验|索引|学习资源|参考文献|参考资料|后记)', label))


def is_removed_junior_chemistry(subject, title, grade):
    if subject != '化学' or not grade.startswith('初中'):
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    label = re.sub(r'^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?', '', label)
    label = re.sub(r'^第\s*[\d一二三四五六七八九十百零〇]+\s*(?:单\s*元|章)\s*', '', label)
    return bool(re.match(r'^(?:其他章节|绪\s*论|整\s*理\s*与\s*(?:提\s*高|提\s*升)|'
                         r'复\s*习\s*与\s*提\s*高|附\s*录)', label))


def is_removed_chapter(subject, title, grade='', sha256=''):
    return (is_removed_math_chapter(subject, title) or is_removed_physics_appendix(subject, title)
            or is_removed_highschool_physics(subject, title, grade)
            or is_removed_junior_chemistry(subject, title, grade)
            or is_removed_highschool_chemistry(subject, title, grade)
            or is_removed_highschool_biology_appendix(subject, title, grade)
            or is_removed_highschool_english_appendix(subject, title, grade)
            or is_removed_junior_english_supplement(subject, title, grade, sha256)
            or is_removed_primary_english_supplement(subject, title, grade, sha256)
            or is_removed_primary_chinese_supplement(subject, title, grade)
            or is_removed_history_supplement(subject, title)
            or is_removed_geography_supplement(subject, title, grade))


def is_removed_primary_chinese_supplement(subject, title, grade):
    if subject != '语文' or not grade.startswith('小学'):
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    label = re.sub(r'^[*◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?', '', label)
    label = re.sub(r'\s+', '', label)
    return bool(re.fullmatch(r'(?:其他章节|识字表|写字表|词语表|笔画名称表|常用偏旁名称表)[.·…]*', label))


def is_removed_primary_english_supplement(subject, title, grade, sha256):
    if subject != '英语' or not grade.startswith('小学'):
        return False
    from app.services.textbook_primary_english import primary_english_chapter_allowed
    return primary_english_chapter_allowed(sha256, title) is False


def is_removed_junior_english_supplement(subject, title, grade, sha256=''):
    # Keep historical grade 9 editions unchanged; extend only the reviewed PDF.
    reviewed_ninth = (grade == '初中九年级' and
        sha256 == '25538732ec8a26780cfad5984fea5bccd7c755aa3a78686e8b10c1f8e2863de0')
    if subject != '英语' or not (re.match(r'^初中[七八]年级', grade) or reviewed_ninth):
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    label = re.sub(r'^[*\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?', '', label)
    # Full labels keep in-unit "Grammar: ..." and "Pronunciation: ..." tasks.
    return bool(re.fullmatch(r'(?:其他章节|reading\s+plus|listening\s+scripts|pronunciation|grammar|'
        r'vocabulary(?:\s+.*)?|reference\s+word\s+list|irregular\s+verbs)', label, re.I))


def is_removed_highschool_english_appendix(subject, title, grade):
    if subject != '英语' or not grade.startswith('高中'):
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    label = re.sub(r'^[*\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?', '', label)
    return bool(re.fullmatch(r'(?:appendices|appendix(?:\s+\w+)?|notes|grammar|'
        r'words\s+and\s+expressions\s+in\s+each\s+unit|vocabulary(?:\s+.*)?|irregular\s+verbs)', label, re.I))


def is_removed_geography_supplement(subject, title, grade=''):
    if subject != '地理':
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    return bool(re.match(r'^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?(?:附\s*录|其\s*他\s*章\s*节|后\s*记)', label)
                or re.fullmatch(r'广东教育出版社有限公司', label)
                or (grade.startswith('初中') and re.match(r'^[【\s]*主\s*题\s*活\s*动', label)))


def is_removed_history_supplement(subject, title):
    if subject != '历史':
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    return bool(re.match(r'^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?(?:附\s*录|其\s*他\s*章\s*节|(?:历\s*史\s*)?译\s*名\s*对\s*照\s*表\s*\(\s*下\s*\))', label))


def is_removed_highschool_biology_appendix(subject, title, grade):
    if subject != '生物' or not grade.startswith('高中'):
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    return bool(re.match(r'^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?附\s*录', label))


def is_removed_highschool_chemistry(subject, title, grade):
    if subject != '化学' or not grade.startswith('高中'):
        return False
    label = unicodedata.normalize('NFKC', title).strip()
    label = re.sub(r'^[*＊◎○●◆◇\s]*(?:\d+(?:\.\d+)*[、.]?\s*)?', '', label)
    # The selectable directory follows the main printed contents only.
    # Sidebar indexes and chapter reviews are not standalone lesson choices.
    return not bool(re.match(r'^(?:第\s*[\d一二三四五六七八九十百零〇]+\s*[章节]|实验活动)', label))


def clean_chapter_title(title):
    """Remove leading PDF directory dots, preserving numbering and every *."""
    cleaned = re.sub(r'^(?:\s*[.．·…])+\s*', '', title)
    cleaned = re.sub(r'^(◎)\s*[.．·…]+\s*', r'\1 ', cleaned)
    # The original PDF's formula font maps y, A and x to unrelated CJK glyphs.
    # Restrict this reviewed correction to the affected 5.6 directory entry.
    if re.fullmatch(r'5\.6\s*函数\s*[狔y]\s*=\s*[犃A]\s*sin\s*\(\s*ω\s*[狓x]\s*\+\s*[φϕ]\s*\)',
                    unicodedata.normalize('NFKC', cleaned).strip()):
        return '5.6 函数 y=Asin(ωx+φ)'
    return cleaned if cleaned.strip() else title


def has_chapter_number(title):
    """Recognize an existing ordinal independently of its punctuation."""
    number = r'[\d一二三四五六七八九十百零〇两]+'
    prefix = r'^[\s*＊◎○●◆◇]*'
    return bool(re.match(prefix + rf'(?:\d|第\s*{number}\s*[章节课单元]|{number}[、，.．\s]|'
                rf'(?:课题|实验活动|跨学科实践活动|跨学科实践|活动|专题|单元)\s*{number}|'
                r'(?:Starter\s+)?(?:Unit|Module|Lesson|Section|Chapter|Topic)\s*\d)', title, re.I))


def format_chapter_number(title):
    """Separate existing ordinals with a space, preserving hierarchy and stars."""
    def punctuate(match):
        marks = ''.join(re.findall(r'[*＊]', match['separator']))
        return match['prefix'] + match['number'].replace('．', '.') + marks + ' '

    separator = r'(?P<separator>[\s.．、，:：*＊]*)'
    # Keep hierarchy numbers such as 1.2 intact and place the separator after
    # the complete number. Chinese chapter labels (第一章) retain their form.
    title = re.sub(r'^(?P<prefix>[\s*＊◎○●◆◇]*)(?P<number>\d+(?:[.．]\d+)*)' + separator,
                   punctuate, title)
    title = re.sub(r'^(?P<prefix>[\s*＊◎○●◆◇]*)(?P<number>[一二三四五六七八九十百零〇两]+)'
                   r'(?=[、，.．\s])' + separator, punctuate, title)
    labels = r'\b(?:Unit|Module|Lesson|Section|Chapter|Topic)\s*'
    title = re.sub(r'(?P<prefix>' + labels + r')(?P<number>\d+(?:[.．]\d+)*)' + separator,
                   punctuate, title, flags=re.I)
    title = re.sub(r'^(?P<prefix>(?:课题|实验活动|跨学科实践活动|跨学科实践|活动|专题|单元)\s*)'
                   r'(?P<number>\d+(?:[.．]\d+)*)' + separator, punctuate, title)
    return title.rstrip()


def numbered_chapter_title(title, position):
    """Format source numbering only; never invent an ordinal from row position."""
    title = clean_chapter_title(title).strip()
    if not title:
        return title
    return format_chapter_number(title)


def school_stage(grade):
    return next((stage for stage in STAGES if (grade or '').startswith(stage)), '')


def grade_matches(selection, grade):
    return not selection or selection == grade or (selection in STAGES and school_stage(grade) == selection)


def filename_metadata(filename):
    match = FILENAME.fullmatch(Path(filename).stem)
    if not match:
        raise ValueError(f'教材文件名不符合“学段+科目+教材名称”：{filename}')
    stage, subject, title = match.groups()
    year = re.match(r'([一二三四五六七八九]+)年级', title)
    grade = stage + year.group() if year else stage
    return dict(title=title, subject=subject, grade=grade, volume=title, publisher='', edition='')


def display_title(book):
    match = FILENAME.fullmatch(Path(book.original_filename).stem)
    if match:
        return match.group(3)
    title = re.sub(r'^(?:普通)?(?:小学|初中|高中|义务教育)(?:教科书|教材)?\s*', '', book.title).strip()
    return re.sub(r'^' + re.escape(book.subject) + r'\s*', '', title).strip() or book.title
