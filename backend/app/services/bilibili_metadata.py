"""Best-effort public metadata. No cookies, private endpoints, or risk-control retries."""
import asyncio
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

import httpx

_cache = {}
_pending = {}
_page_cache = {}
_page_pending = {}


def cover_url(value):
    if not isinstance(value, str) or not value.strip():
        return ''
    try:
        parts = urlsplit('https:' + value if value.startswith('//') else value)
        host = parts.hostname or ''
        if (parts.scheme not in ('http', 'https') or parts.username or parts.password or
            parts.port not in (None, 80, 443) or not parts.path.startswith('/bfs/') or
            not any(host == domain or host.endswith('.' + domain) for domain in ('hdslb.com', 'biliimg.com'))):
            return ''
        return urlunsplit(('https', host, parts.path, parts.query, ''))
    except ValueError:
        return ''


async def _fetch(bvid):
    result = dict(availability='unknown', cover_url='', title='')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4, connect=2), follow_redirects=False) as client:
            response = await client.get('https://api.bilibili.com/x/web-interface/view', params={'bvid': bvid})
        if response.status_code == 404:
            result['availability'] = 'unavailable'
        elif response.status_code == 200:
            data = response.json()
            if data.get('code') in (-404, -62002):
                result['availability'] = 'unavailable'
            elif data.get('code') == 0:
                video = data.get('data') or {}
                if video.get('bvid') == bvid:
                    result.update(availability='available', cover_url=cover_url(video.get('pic')),
                                  title=str(video.get('title') or '')[:256])
        # 412 / 403 / 429 are access restrictions, not evidence of video deletion.
    except (httpx.RequestError, ValueError, TypeError, AttributeError):
        pass
    return _remember(_cache, bvid, result)


class _PageMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cover = ''
        self.title = ''
        self.scripts = []
        self._script_type = None
        self._script_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self._script_type = (attrs.get('type') or '').split(';', 1)[0].strip().lower()
            self._script_parts = []
            return
        if tag != 'meta':
            return
        name = (attrs.get('property') or attrs.get('itemprop') or '').lower()
        content = attrs.get('content') or ''
        if name in ('og:image', 'image') and not self.cover:
            self.cover = cover_url(content)
        elif name == 'og:title' and not self.title:
            self.title = content.strip()[:256]


    def handle_data(self, data):
        if self._script_type is not None:
            self._script_parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self._script_type is not None:
            self.scripts.append((self._script_type, ''.join(self._script_parts)))
            self._script_type = None
            self._script_parts = []


def _thumbnail(value):
    if isinstance(value, list):
        return next((url for item in value if (url := _thumbnail(item))), '')
    if isinstance(value, dict):
        value = value.get('contentUrl') or value.get('url')
    return cover_url(value)


def _video_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from _video_objects(item)
    elif isinstance(value, dict):
        types = value.get('@type', [])
        if isinstance(types, str):
            types = [types]
        if isinstance(types, list) and any(kind in ('VideoObject', 'https://schema.org/VideoObject',
                                                   'http://schema.org/VideoObject') for kind in types):
            yield value
        yield from _video_objects(value.get('@graph'))


def parse_video_page(html, bvid):
    """Adapt thumbnailUrl extraction from bilibili封面提取 to modern video pages."""
    parser = _PageMetadataParser()
    parser.feed(html)
    cover, title = parser.cover, parser.title
    for script_type, script in parser.scripts:
        if script_type == 'application/ld+json':
            try:
                data = json.loads(script)
            except (ValueError, TypeError):
                continue
            for video in _video_objects(data):
                identifiers = ' '.join(str(video.get(key) or '') for key in ('url', '@id', 'embedUrl'))
                video_ids = re.findall(r'BV[0-9A-Za-z]{10}', identifiers)
                if video_ids and bvid not in video_ids:
                    continue
                cover = cover or _thumbnail(video.get('thumbnailUrl'))
                title = title or str(video.get('name') or video.get('headline') or '').strip()[:256]
        else:
            match = re.search(r'(?:window\.)?__INITIAL_STATE__\s*=\s*', script)
            if not match:
                continue
            try:
                data, _ = json.JSONDecoder().raw_decode(script[match.end():].lstrip())
            except ValueError:
                continue
            video = data.get('videoData') if isinstance(data, dict) else None
            if isinstance(video, dict) and video.get('bvid') == bvid:
                cover = cover or cover_url(video.get('pic'))
                title = title or str(video.get('title') or '').strip()[:256]
    return dict(availability='available' if cover else 'unknown', cover_url=cover, title=title)


async def _fetch_page(bvid):
    result = dict(availability='unknown', cover_url='', title='')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4, connect=2), follow_redirects=False) as client:
            response = await client.get(f'https://www.bilibili.com/video/{bvid}/')
        if response.status_code == 404:
            result['availability'] = 'unavailable'
        elif response.status_code == 200:
            result = parse_video_page(response.text, bvid)
        # Restricted pages stay unknown; do not retry them or call the video API.
    except (httpx.RequestError, ValueError):
        pass
    return _remember(_page_cache, bvid, result)


def _remember(cache, bvid, result):
    ttl = 6 * 3600 if result['availability'] == 'available' else 600
    if len(cache) >= 512:
        cache.pop(next(iter(cache)))
    cache[bvid] = (time.monotonic() + ttl, result)
    return result


async def _cached_metadata(bvid, cache, pending, fetch):
    if not re.fullmatch(r'BV[0-9A-Za-z]{10}', bvid):
        return dict(availability='unknown', cover_url='', title='')
    cached = cache.get(bvid)
    if cached and cached[0] > time.monotonic():
        return dict(cached[1])
    if bvid not in pending:
        pending[bvid] = asyncio.create_task(fetch(bvid))
    task = pending[bvid]
    try:
        return dict(await asyncio.shield(task))
    finally:
        if task.done() and pending.get(bvid) is task:
            pending.pop(bvid, None)


async def video_metadata(bvid):
    return await _cached_metadata(bvid, _cache, _pending, _fetch)


async def video_page_metadata(bvid):
    return await _cached_metadata(bvid, _page_cache, _page_pending, _fetch_page)
