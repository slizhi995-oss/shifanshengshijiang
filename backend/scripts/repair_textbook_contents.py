"""Audit all original directories and add missing entries without replacing IDs.

Run from backend with --apply after inspecting outputs/catalog-completeness.
"""
import argparse
import json
import re
import sqlite3
from difflib import SequenceMatcher
from collections import Counter
from pathlib import Path

from app.services.textbook_outline import contents_entries, english_entries, title_key, heading_matches
from app.services.textbook_outline import page_lines, compact
from app.services.textbook_ocr import OCRDocument
from app.services.textbook_catalog import clean_chapter_title, numbered_chapter_title
from scripts.scanned_textbook_contents import reviewed_contents, PDF_OFFSETS

ROOT = Path('outputs/catalog-completeness')


def directory_pages(book):
    number = book['id']
    if number in (66,67): return [6,7]
    if number == 69: return [3,4]
    if number in (98,99,100,103): return [3,4]
    if number in (101,102,104): return [4,5]
    if number == 22: return [4,5]
    if number == 76: return [7,8]
    if number == 68: return [6,7]
    if number in range(43,49): return [5,6] if number==46 else [5,6,7]
    if number in range(49,61): return [5] if number in (49,50,51,53) else [5,6]
    if number in (61,62): return [6,7]
    if number in (63,64,65): return [5]
    if number in (85,86,88,89,90): return [5,6,7,8]
    if number == 87: return list(range(5,16))
    if number in range(91,98): return [5 if number==92 else 4 if number==94 else 6]
    return [p for p in book['diagnostics']['contents_pages'] if p <= (7 if number==109 else 6)]


def render_examples():
    import fitz
    output = ROOT/'previews'
    output.mkdir(exist_ok=True)
    ids = {22:4,8:4,63:5,114:5,90:7,101:4,76:7,36:4}
    for book in json.loads((ROOT/'inventory.json').read_text(encoding='utf-8')):
        if book['id'] not in ids: continue
        number=ids[book['id']]
        with fitz.open(Path('private_textbooks')/book['path']) as doc:
            doc[number-1].get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False).save(output/f'{book["id"]}-{number}.png')


def prepare_ocr():
    import fitz
    jobs=[]
    for book in json.loads((ROOT/'inventory.json').read_text(encoding='utf-8')):
        cache=(ROOT/'directory-ocr'/book['sha']).resolve()
        cache.mkdir(parents=True,exist_ok=True)
        with fitz.open(Path('private_textbooks')/book['path']) as doc:
            for number in directory_pages(book):
                target=cache/f'{number:04}.json'
                page=doc[number-1]
                scale=min(3,2200/max(page.rect.width,page.rect.height))
                image=cache/f'{number:04}.png'
                if not image.exists(): page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).save(image)
                jobs.append(dict(image=str(image),output=str(target),scale=scale,width=page.rect.width,height=page.rect.height,page=number))
    (ROOT/'directory-ocr-jobs.json').write_text(json.dumps(jobs),encoding='utf-8')
    print(f'{len(jobs)} original directory pages prepared',flush=True)


def english_supplements(lines,width,height,book):
    entries=[]
    for line in lines:
        match=re.search(r'\b(?:p\.|page)\s*(\d{1,3})\b',line['text'],re.I)
        if not match: continue
        title=line['text'][:match.start()].strip()
        other=[l for l in lines if l is not line and abs(l['y']-line['y'])<5]
        if not title:
            title=' '.join(l['text'] for l in sorted(other,key=lambda l:l['x']) if not re.search(r'\b(?:p\.|page)\s*\d',l['text'],re.I))
        title=re.sub(r'\b(?:APPENDICES|WORKBOOK)\b','',title,flags=re.I).strip()
        if re.fullmatch(r'unit\s*\d+',title,re.I) and book['file'].startswith('高中'):
            title='Workbook '+title
        elif not title and line['x']>width*.4:
            above=[l for l in lines if 0<line['top']-l['top']<22 and abs(l['x']-line['x'])<width*.3
                and re.search('[A-Za-z]',l['text']) and not re.search(r'\b(?:p\.|page)\s*\d',l['text'],re.I)]
            if above: title=above[-1]['text']
        if not title or len(title)>150 or re.search(r'listening|speaking|reading|writing|structure',title,re.I) and not re.search(r'plus|notes|scripts|vocabulary',title,re.I): continue
        if any(re.search(r'unit\s*\d+',e['title'],re.I) and int(match[1])==e['printed'] for e in entries): continue
        entries.append(dict(title=title,printed=int(match[1])))
    return entries


def ocr_directory_lines(book,number):
    target=ROOT/'directory-ocr'/book['sha']/f'{number:04}.json'
    if not target.exists(): return None
    data=json.loads(target.read_text(encoding='utf-8-sig'))
    lines=[]
    # Preserve the independent columns even when Windows OCR puts both into
    # one line. Word coordinates also separate the title from a distant page.
    split=113<=book['id']<=122
    for line in data['lines']:
        groups=[]
        for word in sorted(line.get('words') or [line],key=lambda w:w['bbox'][0]):
            if not groups or word['bbox'][0]-groups[-1][-1]['bbox'][2]>28 or (split and groups[-1][-1]['bbox'][0]<data['width']*.48<=word['bbox'][0]): groups.append([])
            groups[-1].append(word)
        for group in groups:
            text=' '.join(w['text'] for w in group)
            # Windows segments Chinese into single characters.
            text=re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])','',text)
            bbox=[min(w['bbox'][0] for w in group),min(w['bbox'][1] for w in group),max(w['bbox'][2] for w in group),max(w['bbox'][3] for w in group)]
            lines.append(dict(text=text,x=bbox[0],right=bbox[2],top=bbox[1],y=(bbox[1]+bbox[3])/2,size=(bbox[3]-bbox[1])*.8))
    return lines,data['width'],data['height']


def entries_for(book, texts=None, offset=0):
    reviewed, _ = reviewed_contents(dict(filename=book['file'],sha256=book['sha']))
    entries = list(reviewed or [])
    ocr_entries=[]
    for page in book['front']:
        if page['page'] not in directory_pages(book): continue
        lines, width, height = page['lines'],page['width'],page['height']
        if book['subject']=='英语' and (book['id'] in (85,86,87,88,89,90,98,99,100,101,102,103,104)):
            if reviewed is None: entries.extend(english_entries(lines,width,height))
            continue
        if reviewed is None:
            found = english_entries(lines,width,height) if book['subject']=='英语' else []
            found = found or contents_entries(lines,width,height)
            if book['id'] in (5,6,7,9):
                labels=[l['top'] for l in lines if compact(l['text']) in ('方法导引','探究','研究与实践','化学与职业')]
                if labels:
                    boundary=min(labels)-3
                    found=contents_entries([l for l in lines if l['y']<boundary],width,height)
                    for side in (0,1):
                        subset=[{**l,'x':l['x']-side*width*.48,'right':l['right']-side*width*.48} for l in lines if l['y']>=boundary and (l['x']>=width*.48)==bool(side)]
                        found.extend(contents_entries(subset,width*(.52 if side else .48),height))
            entries.extend(found)
        if book['subject']=='英语': entries.extend(english_supplements(lines,width,height,book))
        ocr=ocr_directory_lines(book,page['page'])
        if ocr and book['subject']!='英语' and reviewed is None:
            ocr_entries.extend(contents_entries(*ocr))
    if texts:
        for entry in ocr_entries:
            if not 1<=entry['printed']+offset<=book['pages']: continue
            body=texts.get(entry['printed']+offset,'')
            if not heading_matches(entry['title'],body[:2000]) or len(re.findall(r'[\u4e00-\u9fff]',entry['title']))<2: continue
            same=[e for e in entries if e['printed']==entry['printed']]
            from difflib import SequenceMatcher
            if any(title_key(e['title'])==title_key(entry['title']) or SequenceMatcher(None,title_key(e['title']),title_key(entry['title'])).ratio()>.76 or (len(title_key(entry['title']))>=3 and title_key(entry['title']) in title_key(e['title'])) for e in same): continue
            # Replace a broken merged label only if the OCR reading is
            # independently present on the printed target page.
            for old in same:
                if not heading_matches(old['title'],body[:2000]) and len(compact(old['title']))>len(compact(entry['title'])):
                    entries.remove(old)
            entries.append(dict(**entry,source='ocr+body'))
    entries=review_corrections(book,entries)
    if texts and book['subject']!='英语':
        keys=' '.join(title_key(e['title']) for e in entries)
        for page in book['front']:
            if page['page'] not in directory_pages(book):continue
            lines=page['lines']
            for index,line in enumerate(lines):
                title=clean_chapter_title(line['text'])
                key=title_key(title)
                if key in keys or len(key)<2 or re.search(r'\d\s*$|[.…·_]{2,}|教育出版社|统编版|北师大|目录|目\s*录|编写|自读|略读|课文原则|必修.*册|标.*课文',title):continue
                # Unnumbered indented pieces and explicit unit/chapter labels
                # are printed in the directory but have no individual page.
                parent=bool(re.fullmatch(r'第[一二三四五六七八九十百]+[单元章]+',title))
                piece=book['subject']=='语文' and (105<=book['id']<=110) and (line.get('size',12)<=10.7 or '/' in title) and line['x']>page['width']*.45 and not re.match(r'^\d',title)
                if not(parent or piece):continue
                starts=[n for n,t in texts.items() if n>max(directory_pages(book)) and any(title_key(part)==key or (parent and compact(title) in compact(part) and len(part)<30) for part in t[:1800].splitlines())]
                if not starts:continue
                # A title must occur in the body itself, not only its author.
                start=min(starts)
                if 0<start-offset<=book['pages']:
                    entries.append(dict(title=title,printed=start-offset,source='unpaged-directory+body'))
                    keys+=' '+key
    unique = {}
    for entry in entries:
        entry['title'] = clean_chapter_title(entry['title'])
        if title_key(entry['title']) in ('目录','目 录','contents') or not 0<entry['printed']<=book['pages']-offset: continue
        unique.setdefault((entry['printed'],title_key(entry['title'])),entry)
    return sorted(unique.values(),key=lambda e:e['printed'])


def review_corrections(book,entries):
    number=book['id']
    if number in (85,86,88,89):
        supplements={
            85: [('*Reading Plus',75),('Listening Scripts',82),('Pronunciation',92),('Grammar',95),('Vocabulary in Each Unit',106),('Vocabulary A–Z',113),('Vocabulary from Primary School',119),('Reference Word List',126)],
            86: [('*Reading Plus',65),('Listening Scripts',74),('Pronunciation',83),('Grammar',88),('Vocabulary in Each Unit',97),('Vocabulary A–Z',106),('Vocabulary from Primary School',115),('Irregular Verbs',118)],
            88: [('*Reading Plus',81),('Listening Scripts',93),('Pronunciation',102),('Grammar',104),('Vocabulary in Each Unit',111),('Vocabulary A–Z',123),('Vocabulary from Primary School',135),('Irregular Verbs',136)],
            89: [('*Reading Plus',81),('Listening Scripts',95),('Grammar',105),('Vocabulary in Each Unit',113),('Vocabulary A–Z',125),('Vocabulary from Primary School',136),('Irregular Verbs',137)],
        }
        entries.extend(dict(title=t,printed=p) for t,p in supplements[number])
    if number==87:
        entries=[e for e in entries if e['printed']<73]
        entries.extend(dict(title=t,printed=p) for t,p in [
            ('Unit 10 You’re supposed to shake hands.',73),('Unit 11 Sad movies make me cry.',81),('Unit 12 Life is full of the unexpected.',89),
            ('Unit 13 We’re trying to save the earth!',97),('Unit 14 I remember meeting all of you in Grade 7.',105),
            ('Notes on the Text',113),('Tapescripts',133),('Grammar',150),('Words and Expressions in Each Unit',156),('Vocabulary Index',171),('Irregular Verbs',184)])
    if number==90:
        entries.extend(dict(title=t,printed=p) for t,p in [('Revision 1',38),('Revision 2',78),('Appendix 1 Chants and songs in each unit',82),('Appendix 2 Vocabulary in each unit',87),('Appendix 3 Vocabulary A-Z',91),('Appendix 4 The English alphabet',95)])
    if number in range(98,105):
        entries=[e for e in entries if not re.search(r'workbook',e['title'],re.I)]
        first=71 if number==98 else 61
        step=6 if number in (98,99,100) else 7
        entries.extend(dict(title=f'Workbook Unit {i+1}',printed=first+i*step) for i in range(5))
        numbers={98:[101,108,112,118,125],99:[91,98,102,109,117],100:[91,98,101,107,114],101:[96,103,106,112,119],102:[96,104,106,112,119],103:[96,105,108,115,122],104:[96,102,106,111,117]}[number]
        entries.extend(dict(title=t,printed=p) for t,p in zip(['Notes','Grammar','Words and Expressions in Each Unit','Vocabulary','Irregular Verbs'],numbers))
        for e in entries:
            e['title']=re.sub(r'\s+WORKBOOK$','',e['title'],flags=re.I)
            if number==102 and e['printed']==25: e['title']='Unit 3 Environmental Protection'
    if number==94:
        for e in entries:
            if e['printed']==26:e['title']='Unit 3 Would you like to come to my birthday party?'
    if number==63:
        entries=[e for e in entries if not (e['printed'] in (1,2) and not re.match(r'第一章|1\.1',e['title']))]
        for e in entries:
            if e['printed']==128:e['title']='探究与发现 为什么 y=±(b/a)x 是双曲线 x²/a²−y²/b²=1 的渐近线'
            if e['printed']==133:e['title']='探究与发现 为什么二次函数 y=ax²+bx+c 的图象是抛物线'
    if number==61:
        for e in entries:
            if e['printed']==92:e['title']='探究与发现 探究函数 y=x+1/x 的图象与性质'
    if number==8:
        entries=[e for e in entries if e['title'] not in ('γ','H + H +')]
    if number==71: entries=[e for e in entries if not(e['printed']==3 and '章' in e['title'])]
    if number==73: entries=[e for e in entries if not(e['printed']==3 and '章' in e['title'])]
    if number==106:
        unit={1:'第一单元',27:'第二单元',59:'第三单元',95:'第四单元',121:'第五单元'}
        for e in entries:
            if e['printed'] in unit:e['title']=unit[e['printed']]
    for e in entries:
        if number==7 and e['printed']==74 and e['title']=='守恒':
            e['title']='电解质溶液中的电荷守恒与元素守恒'
        if number==83 and e['printed']==86 and e['title']=='贡献':
            e['title']='拓展视野 历史不能忘记中国科学家对PCR的贡献'
    return entries


def uncovered():
    books=json.loads((ROOT/'inventory.json').read_text(encoding='utf-8'))
    output=[]
    for book in books:
        if book['subject']=='英语': continue
        keys=' '.join(title_key(e['title']) for e in entries_for(book))
        missed=[]
        for page in book['front']:
            if page['page'] not in directory_pages(book): continue
            for line in page['lines']:
                title=re.sub(r'[.…·_]{2,}.*','',line['text']).strip()
                key=title_key(title)
                if len(re.findall(r'[\u4e00-\u9fff]',key))<2 or key in keys: continue
                if re.search('统编版|北师大|教育出版社|仅供|未经|标.*略读|注:|目录|目 录|课文。',title): continue
                missed.append(f"p{page['page']} {title}")
        if missed: output.append(str(book['id'])+' '+book['file']+'\n'+'\n'.join(missed))
    (ROOT/'uncovered-lines.txt').write_text('\n\n'.join(output),encoding='utf-8')


def audit():
    books = json.loads((ROOT/'inventory.json').read_text(encoding='utf-8'))
    connection = sqlite3.connect('app.db')
    connection.row_factory = sqlite3.Row
    result = []
    for book in books:
        offsets = Counter(c['start_page']-int(c['printed_pages']) for c in book['existing']
            if str(c['printed_pages']).isdigit() and 0<=c['start_page']-int(c['printed_pages'])<=30)
        offset = PDF_OFFSETS.get(book['file'], offsets.most_common(1)[0][0] if offsets else 5)
        texts = {r['page_number']:r['content'] for r in connection.execute('SELECT page_number,content FROM textbook_pages WHERE book_id=?',(book['id'],))}
        entries = entries_for(book,texts,offset)
        anchors = sum(heading_matches(e['title'],texts.get(e['printed']+offset,'')[:1600]) for e in entries)
        source_keys = {(e['printed'],title_key(e['title'])) for e in entries}
        for entry in entries:
            entry['start'] = entry['printed']+offset
            entry['matched'] = [c['id'] for c in book['existing'] if c['start_page']==entry['start'] and title_key(c['title'])==title_key(entry['title'])]
            entry['visible'] = any(c['is_published'] for c in book['existing'] if c['id'] in entry['matched'])
        unmatched = [c for c in book['existing'] if (int(c['printed_pages']) if c['printed_pages'].isdigit() else -1,title_key(c['title'])) not in source_keys]
        result.append(dict(id=book['id'],file=book['file'],sha=book['sha'],toc_pages=directory_pages(book),offset=offset,anchors=anchors,
            entries=entries,unmatched=unmatched,pages=book['pages']))
    (ROOT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'directory-entries.txt').open('w',encoding='utf-8') as output:
        for book in result:
            output.write(f"\n{book['id']} {book['file']} (offset={book['offset']}, anchors={book['anchors']})\n")
            for entry in book['entries']:
                output.write(f"{'OK' if entry['visible'] else 'DRAFT' if entry['matched'] else 'ADD'} {entry['printed']:3} {entry['title']}\n")
            for chapter in book['unmatched']:
                output.write(f"OLD {chapter['printed_pages']} {chapter['title']}\n")
    print(json.dumps(dict(books=len(result),entries=sum(len(b['entries']) for b in result),missing=sum(not e['visible'] for b in result for e in b['entries']),
        weak=[(b['id'],b['file'],b['anchors']) for b in result if b['anchors']<3]),ensure_ascii=False))


def make_plan(apply=False):
    from scripts.import_textbook_library import backup_sqlite, digest
    from app.core.database import engine
    assert engine.url.get_backend_name()=='sqlite'
    assert Path(engine.url.database).resolve()==Path('app.db').resolve()
    books=json.loads((ROOT/'audit.json').read_text(encoding='utf-8'))
    inventory={b['id']:b for b in json.loads((ROOT/'inventory.json').read_text(encoding='utf-8'))}
    connection=sqlite3.connect('app.db')
    connection.row_factory=sqlite3.Row
    plan=dict(books=125,add=[],update=[],hide=[],unresolved=[],coverage=[])
    fields=('title','parent_title','start_page','end_page','printed_pages','content','is_published')
    refs={r[0] for table in ('textbook_assets','textbook_lessons') for r in connection.execute(f'SELECT DISTINCT chapter_id FROM {table} WHERE chapter_id IS NOT NULL')}
    manifest={}
    for book in books:
        book_id=book['id']
        current=connection.execute('SELECT sha256,file_path FROM textbooks WHERE id=?',(book_id,)).fetchone()
        assert current['sha256']==book['sha']
        if apply:assert digest(Path('private_textbooks')/current['file_path'])==book['sha']
        assert book['anchors']>=3
        texts=dict(connection.execute('SELECT page_number,content FROM textbook_pages WHERE book_id=?',(book_id,)))
        old=[dict(r) for r in connection.execute('SELECT * FROM textbook_chapters WHERE book_id=? ORDER BY id',(book_id,))]
        entries=book['entries']
        assigned={}
        used=set()
        # Resolve all exact identities before considering corrected merged rows.
        for index,e in enumerate(entries):
            matches=[c for c in old if c['id'] not in used and title_key(c['title'])==title_key(e['title']) and
                     (c['printed_pages']==str(e['printed']) or c['start_page']==e['start'] or not c['printed_pages'])]
            if matches:
                assigned[index]=matches[0];used.add(matches[0]['id'])
        pairs=[]
        for index,e in enumerate(entries):
            if index in assigned:continue
            for c in old:
                if c['id'] in used or c['printed_pages']!=str(e['printed']):continue
                # Keep every existing starred label intact. Broken mixed rows
                # stay in drafts; the actual starred lesson is added separately.
                if '*' in c['title'] and '*' not in e['title']:continue
                ratio=SequenceMatcher(None,title_key(c['title']),title_key(e['title'])).ratio()
                if ratio>=.42:pairs.append((ratio,index,c))
        for _,index,c in sorted(pairs,key=lambda x:-x[0]):
            if index not in assigned and c['id'] not in used:
                assigned[index]=c;used.add(c['id'])
        expected=[]
        for index,e in enumerate(entries):
            start=e['start']
            later=[x['start'] for x in entries[index+1:] if x['start']>start]
            end=min(later,default=book['pages']+1)-1
            title=e['title']
            # Keep a numbered collection intact when its poems have their own
            # directory rows (which can also share the first printed page).
            if re.search(r'(?:诗[词歌]?|文言文|散文诗|寓言|短诗).*?[二三四五六七八九十\d]+(?:首|则|篇)',title):
                peers=[x for x in entries[index+1:] if x['start']>start and re.match(r'^(?:\d+\s*[* .、]|第.+单元|[◎○]|口语|习作|写作|综合|课外)',x['title'])]
                if peers:end=peers[0]['start']-1
            def content_until(last):return '\n\n'.join(f'[PDF第{n}页]\n{texts[n]}' for n in range(start,last+1))
            content=content_until(end)
            text_length=sum(len(texts[n].strip()) for n in range(start,end+1))
            # Decorative unit opening pages can contain fewer than 40 glyphs.
            # Include the following introductory body page in that range.
            while text_length<40 and end<min(start+2,book['pages']):
                end+=1;content=content_until(end);text_length+=len(texts[end].strip())
            values=dict(title=numbered_chapter_title(title,index+1),parent_title='',start_page=start,end_page=end,printed_pages=str(e['printed']),content=content,is_published=int(40<=text_length and len(content)<=48000))
            existing=assigned.get(index)
            if existing:
                if '*' in existing['title'] and title_key(existing['title'])==title_key(title):values['title']=numbered_chapter_title(existing['title'],index+1)
                # History and existing figure bindings retain their IDs and
                # complete original material ranges.
                asset_pages=[r[0] for r in connection.execute('SELECT pdf_page FROM textbook_assets WHERE chapter_id=?',(existing['id'],))]
                if any(not start<=n<=end for n in asset_pages):
                    values.update(start_page=existing['start_page'],end_page=existing['end_page'],content=existing['content'])
                if existing['parent_title']:values['parent_title']=existing['parent_title']
                changes={f:values[f] for f in fields if existing[f]!=values[f]}
                if changes:plan['update'].append(dict(id=existing['id'],book_id=book_id,values=changes))
            else:
                plan['add'].append(dict(book_id=book_id,**values))
            if not values['is_published']:
                plan['unresolved'].append(dict(book_id=book_id,title=title,start=start,end=end,length=len(content),text=text_length))
            expected.append(dict(title=values['title'],printed=e['printed'],start=values['start_page'],published=bool(values['is_published'])))
        for c in old:
            if c['id'] in used or not c['is_published']:continue
            body='\n'.join(texts.get(n,'') for n in range(c['start_page'],min(c['start_page']+1,book['pages'])+1))
            fragment=len(title_key(c['title']))<4 and any(str(e['printed'])==c['printed_pages'] and len(title_key(e['title']))>8 and title_key(c['title']) in title_key(e['title']) for e in entries)
            if not fragment and heading_matches(c['title'],body[:2200]) and c['start_page']>max(book['toc_pages']):continue
            if c['id'] in refs:
                plan['unresolved'].append(dict(book_id=book_id,id=c['id'],reason='referenced unmatched chapter',title=c['title']))
            else:plan['hide'].append(dict(id=c['id'],book_id=book_id,title=c['title']))
        plan['coverage'].append(dict(book_id=book_id,file=book['file'],directory_entries=expected))
        manifest[book['sha']]=dict(filename=book['file'],contents_pages=book['toc_pages'],offset=book['offset'],
            entries=[dict(title=e['title'],printed=e['printed']) for e in entries])
    preview={**plan,'add':[{k:v for k,v in c.items() if k!='content'} for c in plan['add']],
        'update':[{**c,'values':{k:(f'{len(v)} characters' if k=='content' else v) for k,v in c['values'].items()}} for c in plan['update']]}
    (ROOT/'repair-plan.json').write_text(json.dumps(preview,ensure_ascii=False,indent=2),encoding='utf-8')
    if apply:
        assert not plan['unresolved'],plan['unresolved']
        plan['database_backup']=backup_sqlite(ROOT)
        preserved={table:[tuple(r) for r in connection.execute(f'SELECT * FROM {table} ORDER BY id')] for table in ('textbook_assets','textbook_lessons')}
        old_ids={r[0] for r in connection.execute('SELECT id FROM textbook_chapters')}
        star_labels={r['id']:r['title'] for r in connection.execute("SELECT id,title FROM textbook_chapters WHERE title LIKE '%*%'")}
        try:
            connection.execute('BEGIN IMMEDIATE')
            for c in plan['update']:
                changes=c['values']
                connection.execute('UPDATE textbook_chapters SET '+','.join(f'{key}=?' for key in changes)+' WHERE id=?',(*changes.values(),c['id']))
            for c in plan['add']:
                keys=list(c)
                connection.execute('INSERT INTO textbook_chapters ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',tuple(c.values()))
            for c in plan['hide']:connection.execute('UPDATE textbook_chapters SET is_published=0 WHERE id=?',(c['id'],))
            assert old_ids<={r[0] for r in connection.execute('SELECT id FROM textbook_chapters')}
            assert all(connection.execute('SELECT title FROM textbook_chapters WHERE id=?',(i,)).fetchone()[0].count('*')>=title.count('*') for i,title in star_labels.items())
            assert all([tuple(r) for r in connection.execute(f'SELECT * FROM {t} ORDER BY id')]==rows for t,rows in preserved.items())
            connection.commit()
        except Exception:
            connection.rollback();raise
        target=Path('app/data/textbook_directories.json')
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        (ROOT/'applied.json').write_text(json.dumps({**preview,'database_backup':plan['database_backup']},ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(applied=apply,books=len(books),added=len(plan['add']),updated=len(plan['update']),hidden=len(plan['hide']),unresolved=plan['unresolved'])
    print(json.dumps(summary,ensure_ascii=False))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--prepare-ocr',action='store_true')
    parser.add_argument('--uncovered',action='store_true')
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    make_plan(args.apply) if args.apply or args.plan else prepare_ocr() if args.prepare_ocr else render_examples() if args.render else uncovered() if args.uncovered else audit()
