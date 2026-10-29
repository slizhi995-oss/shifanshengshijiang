"""The adapted command works from any directory without the old scraper dependencies."""
import json
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[2] / 'bilibili封面提取' / 'extract.py'
BV = 'BV12a4y1V7YD'


def test_offline_extraction_from_arbitrary_working_directory(tmp_path):
    environment = tmp_path / '.env'
    environment.write_text('MYSQL_DATABASE=fixture\n', encoding='utf-8')
    source = tmp_path / '视频网页.html'
    source.write_text('<script type="application/ld+json">{"@type":"VideoObject",'
                      '"thumbnailUrl":["//i0.hdslb.com/bfs/archive/test.jpg"],"name":"课堂试讲"}</script>',
                      encoding='utf-8-sig')
    result = subprocess.run([sys.executable, str(SCRIPT), f'https://www.bilibili.com/video/{BV}/?p=2',
                             '--html', str(source)], cwd=tmp_path, capture_output=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['bvid'] == BV
    assert data['cover_url'] == 'https://i0.hdslb.com/bfs/archive/test.jpg'
    assert data['title'] == '课堂试讲'
    assert set(tmp_path.iterdir()) == {source, environment}


def test_no_cover_is_reported_as_failure_without_crashing(tmp_path):
    source = tmp_path / 'restricted.html'
    source.write_text('<html><title>验证页面</title></html>', encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), BV, '--html', str(source)], cwd=tmp_path,
                            capture_output=True, encoding='utf-8', timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)['cover_url'] == ''
    assert '未提取到封面' in result.stderr


def test_invalid_video_is_rejected_before_network_access(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), 'https://evil.test/video/' + BV], cwd=tmp_path,
                            capture_output=True, encoding='utf-8', timeout=10)
    assert result.returncode == 2
    assert '请输入 BV 号' in result.stderr
