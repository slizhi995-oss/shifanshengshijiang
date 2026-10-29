"""Stable, authenticated Markdown image references. No arbitrary image URLs."""
import re
import unicodedata

ASSET_ID_PATTERN = r"tb-[a-f0-9]{32}"
ASSET_IMAGE = re.compile(r"!\[([^\]\n]{1,240})\]\((?:/api/v1/textbooks/assets/|asset://)(" + ASSET_ID_PATTERN + r")(?:/image)?\)")
ANY_IMAGE = re.compile(r"!\[([^\]\n]*)\]\(([^\n)]*)\)")
IMAGE_REQUEST = re.compile(r"\[\[图片[：:]([^\]\n]{1,240})\]\]")


def asset_url(asset_id):
    if not re.fullmatch(ASSET_ID_PATTERN, asset_id):
        raise ValueError("教材素材编号无效")
    return f"/api/v1/textbooks/assets/{asset_id}/image"


def markdown_asset_ids(text):
    return list(dict.fromkeys(match.group(2) for match in ASSET_IMAGE.finditer(text)))


def markdown_image(title, asset_id):
    title = re.sub(r"[\[\]\n]", "", title)[:200]
    return f"![{title}]({asset_url(asset_id)})"


def normalize_figure_text(text):
    text = unicodedata.normalize('NFKC', text)
    text = text.translate(str.maketrans({'\ue010': '.', '\ue011': '-', '−': '-', '–': '-', '—': '-', '‐': '-', '‑': '-'}))
    # OCR commonly reads a short horizontal separator as the Chinese 一.
    return re.sub(r'(?<=\d)\s*一\s*(?=\d)', '-', text)


def figure_tokens(text):
    return {re.sub(r'\s+', '', match.group()) for match in re.finditer(
        r'图\s*\d+(?:\s*[.\-]\s*\d+)*', normalize_figure_text(text))}
