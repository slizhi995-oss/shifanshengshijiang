"""Local video tools that also work with Windows Uvicorn reload's selector loop."""
import asyncio
import shutil
import subprocess


def ffmpeg_executable() -> str:
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as error:
        raise RuntimeError("视频处理组件不可用，请安装后端依赖 imageio-ffmpeg 后重试") from error


async def run_media_tool(command: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    # Windows' SelectorEventLoop cannot launch asyncio subprocesses. Running a
    # synchronous subprocess in a worker thread supports reload without blocking HTTP.
    try:
        return await asyncio.to_thread(
            subprocess.run, command, capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("视频处理超时，请尝试较短的视频或稍后重试") from error
