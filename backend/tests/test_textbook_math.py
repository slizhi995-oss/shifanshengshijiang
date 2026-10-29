"""Mathematics directory headings, including chapters without printed pages."""
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from app.services import textbook_math as maths


def row(index, title):
    return dict(id=index, book_id=45, title=title, parent_title='',
                start_page=index + 7, end_page=index + 7, printed_pages=str(index))


def test_source_headings_without_page_numbers_are_read_from_contents(monkeypatch):
    monkeypatch.setattr(maths, 'reviewed_directory', lambda _: dict(entries=[], contents_pages=[1]))
    lines = [dict(text=text) for text in [
        '第二十一章\u3000一元二次方程', '21.1 一元二次方程 2',
        '第二十二章\u3000二次函数', '22.1 二次函数的图象和性质 28']]
    monkeypatch.setattr(maths, 'fitz', SimpleNamespace(open=lambda _: nullcontext([lines])))
    monkeypatch.setattr(maths, 'page_lines', lambda page: page)
    maths.source_math_chapters.cache_clear()
    assert maths.source_math_chapters('fixture.pdf', 0, 'no-page-headings') == {
        21: '第二十一章 一元二次方程', 22: '第二十二章 二次函数'}
    maths.source_math_chapters.cache_clear()


def test_reviewed_headings_take_precedence_over_pdf_inference(monkeypatch):
    monkeypatch.setattr(maths, 'reviewed_directory', lambda _: dict(entries=[
        dict(title='第四章 数列', printed=1), dict(title='第五章 一元函数的导数及其应用', printed=58)]))
    def unexpected_open(_):
        raise AssertionError('Reviewed chapter headings need no inferred replacement')
    monkeypatch.setattr(maths, 'fitz', SimpleNamespace(open=unexpected_open))
    maths.source_math_chapters.cache_clear()
    assert maths.source_math_chapters('fixture.pdf', 0, 'reviewed-headings') == {
        4: '第四章 数列', 5: '第五章 一元函数的导数及其应用'}
    maths.source_math_chapters.cache_clear()


def test_sections_and_columns_keep_their_chapter_and_appendix_is_separate(monkeypatch):
    monkeypatch.setattr(maths, 'private_path', lambda _: Path('missing-math-fixture.pdf'))
    monkeypatch.setattr(maths, 'source_math_chapters', lambda *_: {
        21: '第二十一章 一元二次方程', 22: '第二十二章 二次函数'})
    chapters = [row(i, title) for i, title in enumerate([
        '21.1 一元二次方程', '阅读与思考 黄金分割数', '小结',
        '复习题21', '22.1 二次函数的图象和性质', '信息技术应用 探索二次函数的性质',
        '部分中英文词汇索引'], 1)]
    original = deepcopy(chapters)
    result = maths.group_math_directory(SimpleNamespace(file_path='fixture.pdf', sha256='fixture'), chapters)
    assert [item['unit_title'] for item in result] == [
        *['第二十一章 一元二次方程'] * 2, *['第二十二章 二次函数'] * 2]
    assert not any(item['is_unit'] for item in result)
    assert [item['id'] for item in result] == [1, 2, 5, 6]
    assert chapters == original


def test_explicit_chapter_cover_is_a_heading_but_primary_topics_stay_selectable(monkeypatch):
    monkeypatch.setattr(maths, 'private_path', lambda _: Path('missing-math-fixture.pdf'))
    monkeypatch.setattr(maths, 'source_math_chapters', lambda *_: {})
    book = SimpleNamespace(file_path='fixture.pdf', sha256='fixture')
    rows = maths.group_math_directory(book, [row(1, '第七章 复数'), row(2, '7.3* 复数的三角表示')])
    assert [item['is_unit'] for item in rows] == [True, False]
    assert [item['unit_title'] for item in rows] == ['第七章 复数'] * 2
    primary = maths.group_math_directory(book, [row(i, title) for i, title in enumerate([
        '20 以内的退位减法', '1 ~6的表内乘法', '1 亿有多大', '1 大数的认识'], 1)])
    assert not any(item['is_unit'] or item['unit_title'] for item in primary)


def test_primary_labels_restore_source_chinese_ordinals_without_numbering_activities():
    def line(text, x, y, right, size=18):
        return dict(text=text, x=x, y=y, right=right, top=y-size/2, size=size)
    lines = [
        line('数学游戏', 220, 100, 320), line('1', 540, 100, 550, 10),
        line('一', 70, 187, 85, 21), line('5以内数的认识和加、减法', 180, 200, 400),
        line('12', 535, 200, 550, 10),
        line('二', 70, 287, 85, 21), line('6~10的认识和加、减法', 180, 300, 400),
        line('34', 535, 300, 550, 10),
        line('欢乐购物街', 220, 400, 320), line('77', 535, 400, 550, 10),
    ]
    labels = maths.primary_directory_labels(lines, 600, 840)
    assert labels[(1, maths.title_key('数学游戏'))] == '☘ 数学游戏'
    assert labels[(12, maths.title_key('5 以内数的认识和加、减法'))] == '一 5以内数的认识和加、减法'
    assert labels[(34, maths.title_key('6~10的认识和加、减法'))] == '二 6~10的认识和加、减法'
    assert labels[(77, maths.title_key('欢乐购物街'))] == '☘ 欢乐购物街'


def test_primary_source_labels_are_display_only_and_keep_every_lesson(monkeypatch):
    monkeypatch.setattr(maths, 'private_path', lambda _: Path('missing-primary-fixture.pdf'))
    monkeypatch.setattr(maths, 'source_primary_math_labels', lambda *_: {
        (1, maths.title_key('认识平面图形')): '一 认识平面图形',
        (2, maths.title_key('20 以内的退位减法')): '二 20以内的退位减法',
    })
    chapters = [row(i, title) for i, title in enumerate([
        '认识平面图形', '20 以内的退位减法', '欢乐购物街'], 1)]
    original = deepcopy(chapters)
    book = SimpleNamespace(file_path='fixture.pdf', sha256='fixture', grade='小学一年级')
    result = maths.group_math_directory(book, chapters)
    assert [item['display_title'] for item in result] == ['一 认识平面图形', '二 20以内的退位减法', '欢乐购物街']
    assert [item['id'] for item in result] == [item['id'] for item in chapters]
    assert not any(item['unit_title'] or item['is_unit'] for item in result)
    assert chapters == original


def test_high_school_columns_return_full_labels_and_inline_indentation(monkeypatch):
    monkeypatch.setattr(maths, 'private_path', lambda _: Path('missing-high-school-fixture.pdf'))
    monkeypatch.setattr(maths, 'source_math_chapters', lambda *_: {1: '第一章 集合与常用逻辑用语'})
    chapters = [row(i, title) for i, title in enumerate([
        '1.3 集合的基本运算', '阅读与思考 集合中元素的个数',
        '信息技术应用：用计算机绘制函数图象', '文献阅读与数学写作\ue012 函数的形成与发展',
        '1.4 充分条件与必要条件', '综合与实践 数学应用'], 1)]
    original = deepcopy(chapters)
    book = SimpleNamespace(file_path='fixture.pdf', sha256='fixture', grade='高中')
    result = maths.group_math_directory(book, chapters)
    assert [item.get('display_title') for item in result] == [
        None, '阅读与思考  集合中元素的个数', '信息技术应用  用计算机绘制函数图象',
        '文献阅读与数学写作*  函数的形成与发展', None, '综合与实践  数学应用']
    assert [item.get('is_nested') for item in result] == [None, True, True, True, None, False]
    assert all(item['unit_title'] == '第一章 集合与常用逻辑用语' for item in result)
    assert [item['id'] for item in result] == [item['id'] for item in chapters]
    assert chapters == original
