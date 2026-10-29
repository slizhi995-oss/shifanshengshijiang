"""Covers and deletion checks must not confuse Bilibili access restrictions with 404."""
import asyncio

import httpx
import pytest

from app.services import bilibili_metadata as metadata

BV = 'BV1E6YZeqEeT'


@pytest.mark.parametrize('html,expected_cover,expected_title', [
    ('<script type="application/ld+json">\n{"@type":"VideoObject",'
     '"thumbnailUrl":["//i0.hdslb.com/bfs/archive/ld.jpg"],"name":"试讲封面"}\n</script>',
     'https://i0.hdslb.com/bfs/archive/ld.jpg', '试讲封面'),
    ('<script type="application/ld+json">{"@graph":[{"@type":["VideoObject"],'
     '"thumbnailUrl":"https://i0.hdslb.com/bfs/archive/graph.jpg"}]}</script>',
     'https://i0.hdslb.com/bfs/archive/graph.jpg', ''),
    ('<script type="application/ld+json">[{"@type":"VideoObject",'
     '"thumbnailUrl":{"@type":"ImageObject","contentUrl":"https://i0.hdslb.com/bfs/archive/object.jpg"}}]</script>',
     'https://i0.hdslb.com/bfs/archive/object.jpg', ''),
    ('<script>window.__INITIAL_STATE__={"videoData":{"bvid":"' + BV + '",'
     '"pic":"//i0.hdslb.com/bfs/archive/state.jpg","title":"当前视频"}};(function(){})();</script>',
     'https://i0.hdslb.com/bfs/archive/state.jpg', '当前视频'),
    ('<script>window.__INITIAL_STATE__={"videoData":{"bvid":"BV12a4y1V7YD",'
     '"pic":"//i0.hdslb.com/bfs/archive/wrong.jpg"}};</script>', '', ''),
    ('<script type="application/ld+json">{"@type":"VideoObject",'
     '"url":"https://www.bilibili.com/video/BV12a4y1V7YD/",'
     '"thumbnailUrl":["https://i0.hdslb.com/bfs/archive/wrong.jpg"]}</script>', '', ''),
    ('<script type="application/ld+json">{"@type":"VideoObject",'
     '"thumbnailUrl":["https://evil.test/image.jpg"]}</script>', '', ''),
    ('<script type="application/ld+json">{broken}</script><script>window.__INITIAL_STATE__=undefined;</script>', '', ''),
    ('<script type="application/ld+json">{"@type":"WebSite",'
     '"thumbnailUrl":"https://i0.hdslb.com/bfs/archive/site.jpg"}</script>', '', ''),
    ('<meta property="og:image" content="https://i0.hdslb.com/bfs/archive/meta.jpg">'
     '<script type="application/ld+json">{"@type":"VideoObject",'
     '"thumbnailUrl":"https://i0.hdslb.com/bfs/archive/ld.jpg"}</script>',
     'https://i0.hdslb.com/bfs/archive/meta.jpg', ''),
])
def test_adapted_extractor_handles_structured_data_and_ignores_other_videos(html, expected_cover, expected_title):
    result = metadata.parse_video_page(html, BV)
    assert result['cover_url'] == expected_cover
    assert result['title'] == expected_title
    assert result['availability'] == ('available' if expected_cover else 'unknown')


@pytest.mark.parametrize('url', ['https://evil.test/a.jpg', 'https://i0.hdslb.com.evil.test/bfs/a.jpg',
    'javascript:alert(1)', 'https://user:pass@i0.hdslb.com/bfs/a.jpg', 'https://i0.hdslb.com:8080/bfs/a.jpg'])
def test_cover_hosts_are_restricted(url):
    assert metadata.cover_url(url) == ''


def test_cover_https_normalization():
    assert metadata.cover_url('//i0.hdslb.com/bfs/archive/cover.jpg') == 'https://i0.hdslb.com/bfs/archive/cover.jpg'


@pytest.mark.asyncio
@pytest.mark.parametrize('status,payload,availability,cover', [
    (200, {'code': 0, 'data': {'bvid': BV, 'pic': '//i0.hdslb.com/bfs/archive/cover.jpg', 'title': '铁丝燃烧实验'}}, 'available', True),
    (200, {'code': -404}, 'unavailable', False), (404, {}, 'unavailable', False),
    (412, {}, 'unknown', False), (403, {}, 'unknown', False), (429, {}, 'unknown', False),
    (200, {'code': 0, 'data': {'bvid': 'different-video', 'pic': '//i0.hdslb.com/bfs/a.jpg'}}, 'unknown', False),
])
async def test_metadata_results_are_cached_and_restrictions_stay_unknown(monkeypatch, status, payload, availability, cover):
    metadata._cache.clear()
    metadata._pending.clear()
    original = httpx.AsyncClient
    calls = []
    async def handler(request):
        calls.append(request)
        assert request.url.host == 'api.bilibili.com' and request.url.params['bvid'] == BV
        return httpx.Response(status, json=payload)
    monkeypatch.setattr(metadata.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    first, second = await asyncio.gather(metadata.video_metadata(BV), metadata.video_metadata(BV))
    assert first == second
    assert first['availability'] == availability and bool(first['cover_url']) == cover
    assert await metadata.video_metadata(BV) == first and len(calls) == 1
    metadata._cache.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize('status,html,availability,expected_cover', [
    (200, '<meta property="og:image" content="//i0.hdslb.com/bfs/archive/cover.jpg">'
          '<meta property="og:title" content="课堂 &amp; 试讲">',
     'available', 'https://i0.hdslb.com/bfs/archive/cover.jpg'),
    (200, "<META content='https://i0.hdslb.com/bfs/archive/cover.jpg?a=1&amp;b=2' property='og:image' />",
     'available', 'https://i0.hdslb.com/bfs/archive/cover.jpg?a=1&b=2'),
    (200, '<meta itemprop="image" content="https://i1.hdslb.com/bfs/archive/cover.jpg">',
     'available', 'https://i1.hdslb.com/bfs/archive/cover.jpg'),
    (200, '<script type="application/ld+json">{"@type":"VideoObject",'
     '"thumbnailUrl":["https://i0.hdslb.com/bfs/archive/ld.jpg"]}</script>',
     'available', 'https://i0.hdslb.com/bfs/archive/ld.jpg'),
    (200, '<meta property="og:image" content="https://evil.test/cover.jpg">', 'unknown', ''),
    (200, '<html><title>验证页面</title></html>', 'unknown', ''),
    (404, '', 'unavailable', ''),
    (412, '<meta property="og:image" content="https://i0.hdslb.com/bfs/archive/cover.jpg">', 'unknown', ''),
    (403, '', 'unknown', ''), (429, '', 'unknown', ''), (302, '', 'unknown', ''),
])
async def test_page_metadata_uses_public_html_and_caches_results(monkeypatch, status, html, availability, expected_cover):
    metadata._page_cache.clear()
    metadata._page_pending.clear()
    original = httpx.AsyncClient
    calls = []

    async def handler(request):
        calls.append(request)
        assert str(request.url) == f'https://www.bilibili.com/video/{BV}/'
        return httpx.Response(status, text=html, headers={'content-type': 'text/html; charset=utf-8'})

    monkeypatch.setattr(metadata.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    first, second = await asyncio.gather(metadata.video_page_metadata(BV), metadata.video_page_metadata(BV))
    assert first == second
    assert first['availability'] == availability
    assert first['cover_url'] == expected_cover
    if 'og:title' in html:
        assert first['title'] == '课堂 & 试讲'
    assert await metadata.video_page_metadata(BV) == first
    assert len(calls) == 1
    metadata._page_cache.clear()


@pytest.mark.asyncio
async def test_page_metadata_network_failure_and_invalid_bvid_are_best_effort(monkeypatch):
    metadata._page_cache.clear()
    original = httpx.AsyncClient
    calls = []

    async def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('fixture timeout', request=request)

    monkeypatch.setattr(metadata.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    empty = dict(availability='unknown', cover_url='', title='')
    assert await metadata.video_page_metadata('../../bad') == empty
    assert calls == []
    assert await metadata.video_page_metadata(BV) == empty
    assert len(calls) == 1
    metadata._page_cache.clear()
