"""Export PDF native images and explicitly selected complete diagrams, without database writes.

Run from backend: python -m scripts.extract_textbook_images --pdf FILE --start-page N
    --end-page N --output DIR [--selection reviewed-selection.json]
Selection entries identify native xrefs or page crops in PDF point coordinates.
"""
import argparse
import hashlib
import html
import io
import json
import shutil
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(pdf, start, end, output, selection=None):
    pdf, output = pdf.resolve(), output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; existing exports are preserved')
    source_sha = digest(pdf)
    chosen = json.loads(selection.read_text(encoding='utf-8')) if selection else {}
    if chosen and chosen.get('source_sha256') != source_sha:
        raise ValueError('Selection belongs to a different source PDF')
    with fitz.open(pdf) as document:
        if document.needs_pass or not 1 <= start <= end <= len(document):
            raise ValueError('PDF is encrypted or page range is invalid')
        output.mkdir(parents=True, exist_ok=True)
        native_dir, teaching_dir = output / 'native', output / 'teaching'
        native_dir.mkdir(); teaching_dir.mkdir()
        images = {}
        for page_number in range(start, end + 1):
            page = document[page_number - 1]
            for entry in page.get_images(full=True):
                xref, mask = entry[:2]
                occurrence = {'pdf_page': page_number,
                              'bboxes': [list(box) for box in page.get_image_rects(xref)]}
                if xref in images:
                    images[xref]['occurrences'].append(occurrence)
                    continue
                pix = fitz.Pixmap(document, xref)
                if pix.colorspace is None:
                    continue  # Stencil masks are PDF drawing components.
                data = document.extract_image(xref)
                picture = Image.open(io.BytesIO(data['image']))
                picture.load()
                if picture.mode not in ('RGB', 'RGBA', 'L', 'LA'):
                    picture = picture.convert('RGB')
                if mask:
                    alpha = Image.open(io.BytesIO(document.extract_image(mask)['image'])).convert('L')
                    if alpha.size != picture.size:
                        alpha = alpha.resize(picture.size, Image.Resampling.LANCZOS)
                    picture = picture.convert('RGBA'); picture.putalpha(alpha)
                filename = f'pdf_{page_number:03d}_xref_{xref}.png'
                destination = native_dir / filename
                picture.save(destination, 'PNG')
                images[xref] = {'xref': xref, 'file': f'native/{filename}',
                               'width': picture.width, 'height': picture.height,
                               'sha256': digest(destination), 'occurrences': [occurrence]}
        teaching = []
        for index, item in enumerate(chosen.get('images', []), 1):
            record = dict(item)
            filename = f'{index:02d}_{item["title"]}.png'
            if any(c in filename for c in '<>:"/\\|?*'):
                raise ValueError('Title contains invalid filename characters')
            destination = teaching_dir / filename
            if item['kind'] == 'native':
                native = images[item['xref']]
                if item['pdf_page'] not in [o['pdf_page'] for o in native['occurrences']]:
                    raise ValueError('Selected native image does not occur on the stated page')
                shutil.copyfile(output / native['file'], destination)
                record['source_file'] = native['file']
            elif item['kind'] == 'crop':
                if not start <= item['pdf_page'] <= end:
                    raise ValueError('Crop page outside requested range')
                page = document[item['pdf_page'] - 1]
                clip = fitz.Rect(item['bbox'])
                if clip.is_empty or not page.rect.contains(clip):
                    raise ValueError('Crop is empty or outside source page')
                dpi = chosen.get('crop_dpi', 180)
                page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), clip=clip,
                                alpha=False).save(destination)
                record['dpi'] = dpi
            else:
                raise ValueError('Unknown selected image kind')
            with Image.open(destination) as picture:
                record.update(width=picture.width, height=picture.height)
                picture.verify()
            record.update(file=f'teaching/{filename}', sha256=digest(destination))
            teaching.append(record)
    result = {'source': {'file': str(pdf), 'sha256': source_sha,
                        'pdf_pages': [start, end], 'title': chosen.get('title', pdf.stem)},
              'native_images': list(images.values()), 'teaching_images': teaching}
    (output / 'images.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    font_path = Path('C:/Windows/Fonts/msyh.ttc')
    font = ImageFont.truetype(str(font_path), 17) if font_path.is_file() else ImageFont.load_default()
    gallery = teaching or list(images.values())
    previews = []
    for batch_start in range(0, len(gallery), 20):
        batch = gallery[batch_start:batch_start + 20]
        canvas = Image.new('RGB', (1600, 290 * ((len(batch) + 3) // 4)), '#E8EDF4')
        for j, record in enumerate(batch):
            with Image.open(output / record['file']) as picture:
                thumb = picture.convert('RGBA')
                white = Image.new('RGBA', thumb.size, 'white'); white.alpha_composite(thumb)
                thumb = white.convert('RGB'); thumb.thumbnail((375, 224))
            x, y = (j % 4) * 400, (j // 4) * 290
            canvas.paste('white', (x + 5, y + 5, x + 395, y + 285))
            canvas.paste(thumb, (x + (400 - thumb.width) // 2, y + 52 + (224 - thumb.height) // 2))
            title = record.get('title', f'xref {record["xref"]}') if 'title' not in record else record['title']
            page = record.get('pdf_page', record.get('occurrences', [{}])[0].get('pdf_page'))
            draw = ImageDraw.Draw(canvas)
            draw.text((x + 12, y + 8), f'{batch_start+j+1:02d} {title}', font=font, fill='#17365D')
            draw.text((x + 12, y + 30), f'PDF {page} | {record["width"]} × {record["height"]}', font=font, fill='#586779')
        filename = f'preview-{batch_start // 20 + 1}.jpg'
        canvas.save(output / filename, quality=94); previews.append(filename)
    cards = ''.join(f'<article><a href="{html.escape(r["file"], quote=True)}"><img src="{html.escape(r["file"], quote=True)}"></a><p>{html.escape(r.get("title",r["file"]))}</p></article>' for r in gallery)
    (output / 'gallery.html').write_text('<!doctype html><meta charset="utf-8"><title>教材图片</title><style>body{font-family:Microsoft YaHei;background:#eef3f9;margin:24px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}article{background:white;padding:16px;border-radius:10px}img{width:100%;height:240px;object-fit:contain}</style><h1>'+html.escape(result['source']['title'])+'</h1><main>'+cards+'</main>', encoding='utf-8')
    return {'output': str(output), 'native_images': len(images), 'teaching_images': len(teaching), 'previews': previews}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--start-page', type=int, required=True)
    parser.add_argument('--end-page', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--selection', type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.pdf, args.start_page, args.end_page, args.output, args.selection), ensure_ascii=False))
