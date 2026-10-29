"""Store administrator-uploaded cover images under the application's uploads directory."""
import hashlib
from io import BytesIO
from pathlib import Path
import re
import warnings
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.services.bilibili_metadata import cover_url

MAX_COVER_BYTES = 5 * 1024 * 1024
_LOCAL_COVER = re.compile(r'/uploads/teaching-tip-covers/([a-f0-9]{64}\.jpg)')


def cover_directory():
    return Path(settings.UPLOAD_DIR).resolve() / 'teaching-tip-covers'


def normalized_cover_url(value):
    match = _LOCAL_COVER.fullmatch(value)
    if match:
        return value if (cover_directory() / match[1]).is_file() else ''
    return cover_url(value)


def is_local_cover(value):
    return bool(_LOCAL_COVER.fullmatch(value))


def store_cover(raw):
    if not raw or len(raw) > MAX_COVER_BYTES:
        raise ValueError('封面图片不能为空，且不能超过 5 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError('请上传 JPG、PNG 或 WebP 图片')
                if source.width * source.height > 20_000_000:
                    raise ValueError('封面图片分辨率过大，请缩小后上传')
                image = ImageOps.exif_transpose(source).convert('RGBA')
                image.thumbnail((1280, 1280))
                background = Image.new('RGB', image.size, 'white')
                background.paste(image, mask=image.getchannel('A'))
                output = BytesIO()
                background.save(output, format='JPEG', quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('图片无法读取，请上传有效的 JPG、PNG 或 WebP 图片') from None
    content = output.getvalue()
    name = hashlib.sha256(content).hexdigest() + '.jpg'
    directory = cover_directory()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / name
    if not destination.exists():
        temporary = directory / (uuid4().hex + '.tmp')
        try:
            temporary.write_bytes(content)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return '/uploads/teaching-tip-covers/' + name
