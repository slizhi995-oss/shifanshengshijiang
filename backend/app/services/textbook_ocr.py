"""Local OCR adapters for the existing corroborated textbook outline parser.

The original PDF is never rewritten. OCR boxes retain PDF coordinates so
contents entries must still match a heading on the actual target body page.
"""
import fitz
import re


class OCRPage:
    def __init__(self, width, height, lines):
        self.rect = fitz.Rect(0, 0, width, height)
        self.lines = [{**line, 'text': re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', line['text'])} for line in lines]

    def get_text(self, option='text', *, clip=None, **kwargs):
        lines = self.lines
        if clip is not None:
            area = fitz.Rect(clip)
            lines = [line for line in lines if area.intersects(fitz.Rect(line['bbox']))]
        lines = sorted(lines, key=lambda line: (round(line['bbox'][1] / 4), line['bbox'][0]))
        if option == 'dict':
            return {'blocks': [{'lines': [{'spans': [dict(text=line['text'], bbox=line['bbox'],
                origin=[line['bbox'][0], line['bbox'][3]], size=(line['bbox'][3]-line['bbox'][1])*.8)]}]} for line in lines]}
        return '\n'.join(line['text'] for line in lines)


class OCRDocument:
    is_ocr = True
    def __init__(self, pages):
        self.pages = [OCRPage(**page) for page in pages]

    def __len__(self):
        return len(self.pages)

    def __iter__(self):
        return iter(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def get_toc(self):
        # Scanning tools' per-page bookmarks aren't textbook chapters.
        return []


def recognize_page(page, engine):
    import numpy as np
    scale = min(2.5, 2000/max(page.rect.width, page.rect.height))
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
    result, _ = engine(pixels[:, :, ::-1], use_cls=False)
    lines = []
    for box, text, score in result or []:
        if score < .5 or not text.strip():
            continue
        xs, ys = zip(*box)
        lines.append(dict(text=text.strip(), score=float(score),
            bbox=[float(min(xs)/scale), float(min(ys)/scale), float(max(xs)/scale), float(max(ys)/scale)]))
    return dict(width=page.rect.width, height=page.rect.height, lines=lines)
