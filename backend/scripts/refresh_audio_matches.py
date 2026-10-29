"""Recompute saved lesson/audio associations without regenerating any lesson."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.core.database import async_session_factory, engine
from app.models.audio_resource import AudioLesson
from app.services.audio_resources import backfill_audio_lessons, match_lesson_audio


async def main():
    try:
        async with async_session_factory() as db:
            await backfill_audio_lessons(db)
            report = []
            for lesson in (await db.execute(select(AudioLesson).order_by(AudioLesson.id))).scalars():
                matches = await match_lesson_audio(db, lesson, force=True)
                if lesson.subject == '英语':
                    report.append(dict(id=lesson.id, title=lesson.title, status=lesson.match_status, count=len(matches)))
            await db.commit()
            print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
