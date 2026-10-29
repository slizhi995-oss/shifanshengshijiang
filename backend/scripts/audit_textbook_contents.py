"""Read-only inventory of original PDF directory pages and existing chapters."""
import json
import sqlite3
from pathlib import Path
import fitz
from app.services.textbook_outline import page_lines, contents_entries, english_entries
from app.services.textbook_ocr import OCRDocument

ROOT = Path('outputs/catalog-completeness')


def inventory():
    books = json.loads((ROOT/'books.json').read_text(encoding='utf-8'))
    connection = sqlite3.connect('app.db')
    connection.row_factory = sqlite3.Row
    result = []
    for book in books:
        with fitz.open(Path('private_textbooks')/book['path']) as original:
            cache = Path('outputs/scanned-textbook-repair/cache')/book['sha']
            document = OCRDocument([json.loads((cache/f'{number:04}.json').read_text(encoding='utf-8-sig'))
                for number in range(1, min(12, len(original))+1)]) if cache.exists() else original
            front = []
            for number, page in enumerate(document, 1):
                if number > (16 if book['id']==87 else 12):
                    break
                lines = page_lines(page)
                front.append(dict(page=number,width=page.rect.width,height=page.rect.height,lines=lines,
                    entries=contents_entries(lines,page.rect.width,page.rect.height),
                    english=english_entries(lines,page.rect.width,page.rect.height) if book['subject']=='英语' else []))
        chapters = [dict(row) for row in connection.execute('SELECT id,title,parent_title,start_page,end_page,printed_pages,is_published,length(content) AS size FROM textbook_chapters WHERE book_id=? ORDER BY start_page,id',(book['id'],))]
        result.append(dict(**book,front=front,existing=chapters))
    (ROOT/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'front-pages.txt').open('w',encoding='utf-8') as output:
        for book in result:
            output.write(f"\n{'='*30} {book['id']} {book['file']}\n")
            for page in book['front']:
                output.write(f"\nPDF {page['page']} [{len(page['entries'])} candidates]\n")
                output.write('\n'.join(line['text'] for line in page['lines'])+'\n')
    print(f'Inventoried {len(result)} books')


if __name__=='__main__':
    inventory()
