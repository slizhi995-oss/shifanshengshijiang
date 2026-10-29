"""Library naming, stage compatibility and corroborated chapter boundaries."""
import fitz
import pytest
from fastapi import HTTPException

from app.services.textbook_catalog import filename_metadata, grade_matches, school_stage, numbered_chapter_title
from app.services.textbook_outline import extract_outline
from app.services.textbook_outline import contents_entries, heading_matches
from app.services import textbook_service as materials
from test_textbook_pipeline import environment, import_reviewed
from test_textbook_pipeline import pdf_bytes
from app.services.textbook_ocr import OCRDocument
from app.services.textbook_outline import english_entries


def test_reviewed_5_6_formula_title_restores_latin_variables():
    expected = '5.6 函数 y=Asin(ωx+φ)'
    assert numbered_chapter_title('5.6 函数狔=犃sin(ω狓+φ)', 1) == expected
    assert numbered_chapter_title('５.６ 函数狔＝犃ｓｉｎ（ω狓＋φ）', 1) == expected
    assert numbered_chapter_title(expected, 1) == expected
    assert numbered_chapter_title('5.7 三角函数的应用', 1) == '5.7 三角函数的应用'


def test_filename_and_stage_compatibility():
    assert filename_metadata('初中道德与法治七年级上册.pdf') == dict(
        title='七年级上册', subject='道德与法治', grade='初中七年级', volume='七年级上册', publisher='', edition='')
    assert filename_metadata('高中历史中外历史纲要(上).pdf')['title'] == '中外历史纲要(上)'
    assert school_stage('高中一年级') == '高中'
    assert grade_matches('高中', '高中一年级')
    assert grade_matches('高中一年级', '高中一年级')
    assert not grade_matches('初中', '高中一年级')
    assert not grade_matches('高中二年级', '高中一年级')
    with pytest.raises(ValueError):
        filename_metadata('unknown.pdf')


@pytest.mark.parametrize('reviewed', [False, True])
def test_contents_pages_are_mapped_to_body_headings(reviewed):
    with fitz.open() as doc:
        for index in range(7):
            page = doc.new_page()
            if index == 1:
                page.insert_text((50, 50), 'Contents', fontsize=18)
                for y, title, number in [(110, '1.1 First Law', '1'), (140, '1.2 Motion', '2'), (170, '1.3 Forces', '3')]:
                    page.insert_text((50, y), title, fontsize=14)
                    page.insert_text((480, y), number)
            if index >= 3:
                title = ['1.1 First Law', '1.2 Motion', '1.3 Forces', 'Review'][index-3]
                page.insert_text((50, 70), title, fontsize=20)
                page.insert_text((50, 110), 'Corroborated textbook body text. ' * 4)
                page.insert_text((280, 820), str(index-2))
        review = [dict(title=title, printed=index) for index, title in enumerate(['First Law', 'Motion', 'Forces'], 1)]
        texts, chapters, diagnostics = extract_outline(doc, '物理', review if reviewed else None)
    assert len(texts) == 7
    assert diagnostics['contents_pages'] == [2]
    assert [(c['start_page'], c['end_page']) for c in chapters] == [(4, 4), (5, 5), (6, 7)]
    assert all(c['is_published'] for c in chapters)
    assert [c['title'] for c in chapters] == ['1.1 First Law', '1.2 Motion', '1.3 Forces']
    assert '[PDF第4页]' in chapters[0]['content']


def test_empty_scan_does_not_become_published_chapter():
    with fitz.open() as doc:
        for _ in range(5):
            doc.new_page()
        doc.set_toc([[1, 'First Law', 3]])
        _, chapters, _ = extract_outline(doc, '物理')
    assert not any(c['is_published'] for c in chapters)


def test_two_contents_columns_and_slash_page_layout():
    lines = [dict(text=f'{name} ........ {number}',x=x,right=x+300,y=y)
             for x, names in [(40,['Spring','Summer','Autumn']),(540,['Winter','Review','Index'])]
             for y,name,number in zip([100,140,180],names,[1,5,9] if x==40 else [12,16,20])]
    entries = contents_entries(lines,1000,800)
    assert [entry['title'] for entry in entries] == ['Spring','Summer','Autumn','Winter','Review','Index']
    slash = [dict(text=f'第{number}节 温度 / {number*5}',x=200,right=390,y=number*30) for number in range(1,5)]
    assert [entry['printed'] for entry in contents_entries(slash,1000,800)] == [5,10,15,20]


def test_pinyin_between_primary_reading_title_glyphs():
    assert heading_matches('2 找春天', '找 zhao 春 chun 天 tian\n正文')
    assert not heading_matches('2 找春天','古诗二首\n另一篇课文')


def test_offcentre_directory_columns_trailing_dots_and_star_spans():
    lines=[]
    for x,names,numbers in [(45,['13. 花钟','14. 蜜蜂','15. 小虾'],[48,51,54]),
                            (260,['22. 我们奇妙的世界','23. 海底世界','24. 火烧云'],[86,89,91])]:
        for y,name,number in zip([80,104,128],names,numbers):
            lines.append(dict(text=f'{name}..........{number}.',x=x,right=x+188,y=y,size=13))
    lines.append(dict(text='*',x=59,right=64,y=128,size=9))
    entries=contents_entries(sorted(lines,key=lambda l:l['y']),521.575,737)
    assert [(e['title'],e['printed']) for e in entries]==[
        ('13. 花钟',48),('14. 蜜蜂',51),('15* . 小虾',54),
        ('22. 我们奇妙的世界',86),('23. 海底世界',89),('24. 火烧云',91)]


def test_same_page_directory_rows_survive_and_collection_keeps_all_poems():
    def page(items):
        return dict(width=600,height=840,lines=[dict(text=text,bbox=[40,y,500,y+20]) for y,text in items])
    pages=[page([]) for _ in range(9)]
    for index,title in [(3,'1 古诗三首 First poem'),(4,'Second poem'),(5,'Third poem'),(6,'2 Next lesson')]:
        pages[index]=page([(80,title),(160,'Textbook body '*30)])
    directory=[dict(title=t,printed=p) for t,p in [('1 古诗三首',1),('First poem',1),('Second poem',2),('Third poem',3),('2 Next lesson',4)]]
    _,chapters,_=extract_outline(OCRDocument(pages),'语文',directory,[2,3],3)
    assert len(chapters)==5
    assert [(c['title'],c['start_page'],c['end_page']) for c in chapters[:2]]==[
        ('1 古诗三首',4,6),('First poem',4,4)]
    assert all(c['is_published'] for c in chapters)


def test_ocr_reviewed_offset_ignores_repeated_running_headers():
    def page(lines):
        return dict(width=600,height=840,lines=[dict(text=text,bbox=[40,y,500,y+20]) for y,text in lines])
    pages=[page([]) for _ in range(8)]
    pages[3]=page([(80,'First Law'),(160,'Textbook body '*20),(810,'1')])
    pages[4]=page([(20,'First Law'),(160,'Continuation '*20),(810,'2')])
    pages[5]=page([(80,'Motion'),(160,'Textbook body '*20),(810,'3')])
    pages[6]=page([(20,'Motion'),(160,'Continuation '*20),(810,'4')])
    pages[7]=page([(80,'Forces'),(160,'Textbook body '*20),(810,'5')])
    contents=[dict(title=title,printed=number) for title,number in [('First Law',1),('Motion',3),('Forces',5)]]
    _,chapters,_=extract_outline(OCRDocument(pages),'物理',contents,[2,3],3)
    assert [(chapter['start_page'],chapter['end_page']) for chapter in chapters]==[(4,5),(6,7),(8,8)]
    assert all(chapter['is_published'] for chapter in chapters)
    assert [chapter['title'] for chapter in chapters] == ['First Law', 'Motion', 'Forces']


@pytest.mark.parametrize('title, expected', [
    ('1 春天', '1 春天'), ('1春天', '1 春天'), ('1.春天', '1 春天'),
    ('1． 春天', '1 春天'), ('1、春天', '1 春天'),
    ('1.2 运动', '1.2 运动'), ('1.2. 运动', '1.2 运动'),
    ('第 一 章 运动', '第 一 章 运动'), ('第二单元', '第二单元'),
    ('一、观察', '一 观察'), ('Unit 2 Family', 'Unit 2 Family'),
    ('Section 1 Meeting English', 'Section 1 Meeting English'),
    ('课题1 空气', '课题1 空气'), ('实验活动2 制氧', '实验活动2 制氧'),
    ('3* 雨', '3* 雨'), ('13* . 花钟', '13* 花钟'), ('*13 花钟', '*13 花钟'),
    ('Unit 1 Family · Lesson 2 Happy Weekend', 'Unit 1 Family · Lesson 2 Happy Weekend'),
])
def test_existing_directory_numbers_are_preserved(title, expected):
    assert numbered_chapter_title(title, 9) == expected
    assert numbered_chapter_title(expected, 9) == expected


def test_missing_directory_numbers_and_stars():
    title = numbered_chapter_title('… *Reading Plus', 4)
    assert title == '*Reading Plus'
    assert numbered_chapter_title(title, 9) == title


def test_separate_lesson_numbers_are_not_discarded():
    lines = [dict(text=text, x=x, right=right, y=100, size=14)
             for text, x, right in [('13', 40, 60), ('*', 64, 70), ('花钟', 80, 180), ('48', 500, 520)]]
    assert contents_entries(lines, 600, 800) == [dict(title='13* 花钟', printed=48)]


def test_existing_labels_restore_numbers_from_printed_page_ranges(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scripts import number_chapter_titles as migration
    source = tmp_path / 'numbered.pdf'
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((40, 100), '3')
        page.insert_text((80, 100), 'Motion')
        page.insert_text((500, 100), '15')
        document.save(source)
    monkeypatch.setattr(migration, 'private_path', lambda _: source)
    monkeypatch.setattr(migration, 'reviewed_directory', lambda _: None)
    chapters = [SimpleNamespace(id=2, title='Motion', printed_pages='15–20', start_page=20)]
    book = SimpleNamespace(sha256='test', file_path='numbered.pdf')
    assert [title for _, title in migration.proposed_titles(book, chapters)] == ['3 Motion']
    chapters[0].title = '3. Motion'
    assert [title for _, title in migration.proposed_titles(book, chapters)] == ['3 Motion']


def test_english_combined_unit_labels_keep_multiline_theme():
    lines=[]
    for index,title in enumerate(['CULTURAL HERITAGE','WILDLIFE PROTECTION','THE INTERNET']):
        y=100+index*140
        for text,x,right,top,size in [(f'UNIT{index+1}',90,135,y,13),(f'p.{1+index*12}',50,80,y+35,10),
                                     (title,90,210,y+25,16),('Listening task',250,370,y+25,10)]:
            lines.append(dict(text=text,x=x,right=right,y=top+size/2,top=top,size=size))
    assert english_entries(lines,650,840)==[
        dict(title='Unit 1 CULTURAL HERITAGE',printed=1),dict(title='Unit 2 WILDLIFE PROTECTION',printed=13),dict(title='Unit 3 THE INTERNET',printed=25)]


@pytest.mark.asyncio
async def test_stage_filter_and_generation_compatibility(environment):
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    response = await client.get('/textbooks', params={'subject': '物理', 'stage': '高中'})
    assert [b['id'] for b in response.json()['data']] == [book['id']]
    assert response.json()['data'][0]['stage'] == '高中'
    assert not (await client.get('/textbooks', params={'catalog_only': True})).json()['data']
    assert not (await client.get('/textbooks', params={'stage': '初中'})).json()['data']
    assert (await client.get('/textbooks', params={'stage': '大学'})).status_code == 422
    assert (await client.get('/textbooks/recommend', params={'subject': '物理', 'grade': '高中'})).json()['data'][0]['id'] == chapter['id']
    async with sessions() as db:
        confirmed, source = await materials.confirmed_chapter(db, chapter['id'], '物理', '高中')
        assert confirmed.id == chapter['id']
        with pytest.raises(HTTPException):
            await materials.confirmed_chapter(db, chapter['id'], '物理', '初中')


@pytest.mark.asyncio
async def test_library_import_is_idempotent_and_preserves_chapters(environment, monkeypatch):
    from scripts import import_textbook_library as importer
    from app.models.textbook import Textbook, TextbookChapter, TextbookPage
    from sqlalchemy import select, func
    client, sessions, root = environment
    monkeypatch.setattr(importer, 'async_session_factory', sessions)
    source = root / '高中物理必修第一册.pdf'
    source.write_bytes(pdf_bytes())
    sha = importer.digest(source)
    parsed = dict(pages=['First page body', 'Second page body'], status='ready', chapters=[dict(
        title='First Law', parent_title='', start_page=1, end_page=2, printed_pages='',
        content='Textbook body for the first law, sufficiently long for generation.', is_published=True)])
    first = await importer.import_book(source, sha, filename_metadata(source.name), parsed)
    async with sessions() as db:
        chapter = (await db.execute(select(TextbookChapter))).scalar_one()
        chapter_id = chapter.id
        chapter.title = 'Human corrected title'
        await db.commit()
    second = await importer.import_book(source, sha, filename_metadata(source.name), parsed)
    assert first['book_id'] == second['book_id']
    assert second['reused']
    async with sessions() as db:
        assert (await db.execute(select(func.count()).select_from(Textbook))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(TextbookPage))).scalar_one() == 2
        chapters = (await db.execute(select(TextbookChapter))).scalars().all()
        assert [(c.id, c.title) for c in chapters] == [(chapter_id, 'Human corrected title')]
    response = await client.get('/textbooks', params={'subject': '物理', 'stage': '高中', 'catalog_only': True})
    assert response.json()['data'][0]['display_title'] == '必修第一册'


@pytest.mark.asyncio
@pytest.mark.parametrize(('old_name', 'correct_name'), [
    ('小学英语五年级下册.pdf', '小学英语四年级下册.pdf'),
    ('小学英语六年级下册.pdf', '小学英语五年级下册.pdf'),
    ('小学英语四年级下册.pdf', '小学英语六年级下册.pdf'),
])
async def test_renamed_volume_updates_all_metadata_without_replacing_content(environment, monkeypatch, old_name, correct_name):
    from scripts import import_textbook_library as importer
    from app.models.textbook import Textbook, TextbookChapter, TextbookPage
    from sqlalchemy import select
    client, sessions, root = environment
    monkeypatch.setattr(importer, 'async_session_factory', sessions)
    source = root/old_name
    source.write_bytes(pdf_bytes())
    sha = importer.digest(source)
    parsed = dict(pages=['First page body', 'Second page body'], status='ready', chapters=[dict(
        title='Unit 1 Original content', parent_title='', start_page=1, end_page=2, printed_pages='',
        content='Original textbook content. '*4, is_published=True)])
    original = await importer.import_book(source, sha, filename_metadata(old_name), parsed)
    async with sessions() as db:
        chapter = (await db.execute(select(TextbookChapter))).scalar_one()
        old_chapter = (chapter.id, chapter.book_id, chapter.title, chapter.content)
        old_pages = [(row.id, row.book_id, row.page_number, row.content)
            for row in (await db.execute(select(TextbookPage).order_by(TextbookPage.id))).scalars()]
    corrected_source = source.rename(root/correct_name)
    for _ in range(2):
        result = await importer.import_book(corrected_source, sha, filename_metadata(correct_name), parsed)
        assert result['reused'] and result['book_id'] == original['book_id']
    metadata = filename_metadata(correct_name)
    async with sessions() as db:
        book = (await db.execute(select(Textbook))).scalar_one()
        assert (book.title, book.grade, book.volume, book.original_filename) == (
            metadata['title'], metadata['grade'], metadata['volume'], correct_name)
        chapter = (await db.execute(select(TextbookChapter))).scalar_one()
        assert (chapter.id, chapter.book_id, chapter.title, chapter.content) == old_chapter
        assert [(row.id, row.book_id, row.page_number, row.content)
            for row in (await db.execute(select(TextbookPage).order_by(TextbookPage.id))).scalars()] == old_pages
    response = await client.get('/textbooks', params={'subject': '英语', 'grade': metadata['grade']})
    assert [row['id'] for row in response.json()['data']] == [original['book_id']]
    assert response.json()['data'][0]['display_title'] == metadata['title']
    old_grade = filename_metadata(old_name)['grade']
    assert (await client.get('/textbooks', params={'subject': '英语', 'grade': old_grade})).json()['data'] == []


def test_reviewed_primary_volume_filenames_match_audited_content():
    from scripts.repair_primary_english_volumes import VOLUMES
    from app.services.textbook_outline import reviewed_directory
    for sha, filename in VOLUMES.items():
        assert reviewed_directory(sha)['filename'] == filename


@pytest.mark.asyncio
async def test_same_page_options_follow_original_directory_order(environment, monkeypatch):
    from app.api.routes import textbooks
    from test_textbook_pipeline import ADMIN, CHAPTER_TEXT
    client, sessions, root = environment
    book, chapter, image, other = await import_reviewed(client)
    response=await client.post(f'/textbooks/{book["id"]}/chapters',headers=ADMIN,json=dict(
        title='Chapter overview',start_page=chapter['start_page'],end_page=chapter['end_page'],content=CHAPTER_TEXT,is_published=True))
    assert response.status_code==201,response.text
    added=response.json()['data']
    monkeypatch.setattr(textbooks,'reviewed_directory',lambda sha:dict(offset=0,entries=[
        dict(title='Chapter overview',printed=chapter['start_page']),dict(title=chapter['title'],printed=chapter['start_page'])]))
    rows=(await client.get(f'/textbooks/{book["id"]}/chapters')).json()['data']
    same_page=[c['id'] for c in rows if c['start_page']==chapter['start_page']]
    assert same_page.index(added['id'])<same_page.index(chapter['id'])
