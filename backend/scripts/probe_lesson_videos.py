"""Manual live smoke check. Uses configured credentials; never prints keys."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import select
from app.core.database import async_session_factory, engine
from app.models.audio_resource import AudioLesson
from app.models.lesson_video import LessonVideo, LessonVideoSearch, LessonWebResource
from app.services.lesson_videos import (
    VideoSearchError, bocha_search, configured, normalize_candidates, queue_search, run_search, search_state,
)


async def main(args):
    if not configured():
        raise SystemExit('请先在 backend/.env.local 配置 BOCHA_API_KEY')
    if args.query:
        rows = await bocha_search(args.query)
        valid = normalize_candidates(rows, dict(id='probe', section='人工检索验证', purpose=args.query))
        result = dict(query=args.query, returned=len(rows), valid_videos=len(valid),
                      resources=[dict(title=item['title'], url=item['url'], resource_type=item['resource_type'], site_name=item['site_name']) for item in valid])
    elif args.lesson_id:
        async with engine.begin() as conn:
            for table in (LessonVideoSearch.__table__, LessonVideo.__table__, LessonWebResource.__table__):
                await conn.run_sync(lambda sync, table=table: table.create(sync, checkfirst=True))
        async with async_session_factory() as db:
            lesson = await db.get(AudioLesson, args.lesson_id)
            if not lesson:
                raise SystemExit('教案资源不存在')
            lesson_id, user_id = lesson.id, lesson.user_id
            run_id = await queue_search(db, lesson, force=args.refresh)
        if run_id:
            await run_search(engine, lesson_id, user_id, run_id)
        async with async_session_factory() as db:
            lesson = await db.get(AudioLesson, lesson_id)
            result = await search_state(db, lesson)
    else:
        async with async_session_factory() as db:
            rows = (await db.execute(select(AudioLesson).order_by(AudioLesson.id.desc()).limit(15))).scalars().all()
            result = [dict(id=row.id, title=row.title, subject=row.subject, grade=row.grade) for row in rows]
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding='utf-8')
    print(text)
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', help='只测试真实网页搜索，不调用文本模型')
    parser.add_argument('--lesson-id', type=int, help='对现有教案运行完整后台推荐流程，并保存缓存')
    parser.add_argument('--output', help='保存脱敏结果 JSON')
    parser.add_argument('--refresh', action='store_true', help='重新检索，不使用已有缓存')
    try:
        asyncio.run(main(parser.parse_args()))
    except VideoSearchError as exc:
        raise SystemExit(str(exc)) from None
