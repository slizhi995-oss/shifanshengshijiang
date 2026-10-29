"""Run from backend: python scripts/import_audio_library.py [--source <directory>]."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.models import Base
from app.services.audio_resources import import_audio_catalog


async def main():
    parser = argparse.ArgumentParser(description='校验英语音频、建立文本向量索引并关联历史教案')
    parser.add_argument('--source', help='包含分册目录和音频检索元数据.jsonl的音频源文件目录')
    args = parser.parse_args()
    if args.source:
        settings.AUDIO_SOURCE_DIR = str(Path(args.source).resolve())
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_session_factory() as db:
            report = await import_audio_catalog(db)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
