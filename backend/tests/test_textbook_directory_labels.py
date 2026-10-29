"""Labels must match the printed table, without artificial row ordinals."""
from types import SimpleNamespace

from app.services.textbook_catalog import numbered_chapter_title
from app.services.textbook_outline import contents_entries, reconcile_directory_entries, title_key
from scripts import number_chapter_titles as migration


def row(text, y, x=40, right=560):
    return dict(text=text, x=x, right=right, y=y, top=y-8, size=14)


def test_directory_gardens_and_unnumbered_poems_never_get_sequence_numbers():
    for label in ['◎ 语文园地二', '我是中国人', '池上', '*Reading Plus']:
        assert numbered_chapter_title(label, 15) == label
    assert numbered_chapter_title('1 a o e', 999) == '1 a o e'
    assert numbered_chapter_title('5 g k h', 1) == '5 g k h'


def test_original_numbers_and_symbols_override_generated_numbers():
    reviewed = [dict(title='a o e', printed=20), dict(title='◎ 语文园地二', printed=28)]
    native = [dict(title='1 a o e', printed=20), dict(title='◎ 语文园地二', printed=28)]
    assert reconcile_directory_entries(reviewed, native) == [
        dict(title='1 a o e', printed=20), dict(title='◎ 语文园地二', printed=28)]


def test_wrapped_unit_themes_are_complete():
    lines = [row('第一单元 从中华文明起源到秦汉统一多民族封建国家', 80),
             row('的建立与巩固', 110, right=380), row('1', 110, x=520)]
    assert contents_entries(lines, 600, 840) == [dict(
        title='第一单元 从中华文明起源到秦汉统一多民族封建国家 的建立与巩固', printed=1)]


def test_wrapped_subtitle_with_separate_leader_keeps_its_prefix():
    lines = [row('阅读与思考 统计学在军事中的应用', 80),
             row('——二战时德国坦克总量的估计问题', 110), row('..................210', 140)]
    assert contents_entries(lines, 600, 840) == [dict(
        title='阅读与思考 统计学在军事中的应用 ——二战时德国坦克总量的估计问题', printed=210)]


def test_restore_removes_an_invented_number_and_applies_audited_missing_glyph(tmp_path, monkeypatch):
    monkeypatch.setattr(migration, 'private_path', lambda _: tmp_path/'missing.pdf')
    monkeypatch.setattr(migration, 'reviewed_directory', lambda _: dict(offset=5, entries=[
        dict(title='◎ 语文园地二', printed=28), dict(title='5 g k h', printed=32, source_aliases=['g h'])]))
    chapters = [SimpleNamespace(id=1, title='15. ◎ 语文园地二', printed_pages='28', start_page=33),
                SimpleNamespace(id=2, title='5. g h', printed_pages='32', start_page=37)]
    book = SimpleNamespace(sha256='verified-fixture', file_path='missing.pdf')
    assert [title for _, title in migration.proposed_titles(book, chapters)] == ['◎ 语文园地二', '5 g k h']


def test_duplicate_fragment_is_unpublished_and_complete_original_keeps_its_id(monkeypatch):
    title = '第一单元 文明的建立与巩固'
    monkeypatch.setattr(migration, 'reviewed_directory', lambda _: dict(offset=5, entries=[dict(title=title, printed=1)]))
    complete = SimpleNamespace(id=10, title=title, start_page=6, is_published=True)
    fragment = SimpleNamespace(id=20, title='1. 的建立与巩固', start_page=6, is_published=True)
    hidden = migration.duplicate_rows(SimpleNamespace(id=1, sha256='fixture'), [(complete, title), (fragment, title)])
    assert [row['id'] for row in hidden] == [20]


def test_nested_generated_prefix_does_not_obscure_original_lesson_identity():
    assert title_key('2. 阅读 1 春 / 朱自清') == title_key('1 春 / 朱自清')


def test_mixed_previous_poem_is_not_an_extra_directory_choice(monkeypatch):
    title = '13* 与朱元思书 / 吴均'
    monkeypatch.setattr(migration, 'reviewed_directory', lambda _: dict(offset=7, entries=[dict(title=title, printed=67)]))
    correct = SimpleNamespace(id=20, title=title, start_page=74, is_published=True)
    mixed = SimpleNamespace(id=10, title='27. 记承天寺夜游 / 苏轼 13* 与朱元思书 / 吴均', start_page=73, is_published=True)
    hidden = migration.duplicate_rows(SimpleNamespace(id=1, sha256='fixture'), [(mixed, mixed.title), (correct, title)])
    assert [row['id'] for row in hidden] == [10]
