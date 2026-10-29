import asyncio
import subprocess
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routes import video_analysis as routes
from app.services import media_tools
from app.services.video_analysis_service import VideoAnalysisService


def test_real_video_processing_on_selector_loop_without_system_ffmpeg(tmp_path, monkeypatch):
    """Match Windows Uvicorn --reload, including a fresh install without PATH tools."""
    monkeypatch.setattr(media_tools.shutil, "which", lambda _name: None)
    source = tmp_path / "试讲视频.mp4"
    loop = asyncio.SelectorEventLoop()
    try:
        generated = loop.run_until_complete(media_tools.run_media_tool([
            media_tools.ffmpeg_executable(), "-v", "error", "-y",
            "-f", "lavfi", "-i", "color=c=blue:size=160x90:rate=5:duration=1",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-t", "1", "-c:v", "mpeg4", "-c:a", "aac", str(source),
        ], timeout=30))
        assert generated.returncode == 0, generated.stderr
        service = VideoAnalysisService()
        duration = loop.run_until_complete(service._get_video_duration(str(source)))
        assert 0.9 <= duration <= 1.2
        audio = loop.run_until_complete(service._extract_audio(str(source)))
        with wave.open(audio) as recording:
            assert recording.getframerate() == 16000
            assert recording.getnchannels() == 1
            assert recording.getnframes() > 0
        frames = loop.run_until_complete(service._extract_key_frames(str(source), duration))
        assert len(frames) == 1
        assert (tmp_path / "试讲视频_frame_0.jpg").stat().st_size > 0
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_invalid_video_returns_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(media_tools.shutil, "which", lambda _name: None)
    source = tmp_path / "broken.mp4"
    source.write_bytes(b"broken video")
    with pytest.raises(RuntimeError, match="无法读取视频时长"):
        await VideoAnalysisService()._get_video_duration(str(source))


@pytest.mark.asyncio
async def test_empty_processing_exception_is_not_returned_as_blank_error(tmp_path, monkeypatch):
    source = tmp_path / "temporary.mp4"
    source.write_bytes(b"test")
    monkeypatch.setitem(routes._standalone_analysis_results, "failed-task", {"status": "processing", "user_id": 1})
    monkeypatch.setattr(routes, "get_video_analysis_service", lambda: SimpleNamespace(
        analyze_video=AsyncMock(side_effect=NotImplementedError())))
    await routes._analyze_standalone_video("failed-task", str(source))
    result = routes._standalone_analysis_results["failed-task"]
    assert result["status"] == "failed"
    assert "NotImplementedError" in result["error"]
    assert not source.exists()
