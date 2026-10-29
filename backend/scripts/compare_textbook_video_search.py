"""Compare lesson-only and textbook-assisted keywords using the same Bilibili pipeline.

Live provider calls cost credits. Results are saved after each branch for resumability;
production recommendation caches and lesson contents are never changed.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.core.database import async_session_factory, engine
from app.models.audio_resource import AudioLesson
from app.services.lesson_videos import (VideoSearchError, bocha_search, configured, extract_needs,
    fingerprint, normalize_candidates, rank_candidates, textbook_context)


async def compare(lesson_id, output_dir):
    output = output_dir / f'lesson-{lesson_id}.json'
    result = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
    async with async_session_factory() as db:
        lesson = await db.get(AudioLesson, lesson_id)
        if not lesson:
            raise ValueError('教案不存在')
        db.expunge(lesson)
        context = await textbook_context(db, lesson)
        if not context:
            raise ValueError('教案没有有效的对应教材小节')
        revision = fingerprint(lesson, context)
        if result and result.get('fingerprint') != revision:
            raise ValueError('教案或教材已变更，请使用新的输出目录')
        result.update(lesson_id=lesson.id, title=lesson.title, fingerprint=revision,
            textbook={key: context[key] for key in ('book_title', 'chapter_title', 'printed_pages')})
        search_cache = result.setdefault('search_responses', {})
        def save():
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        for mode, textbook in [('lesson_only', None), ('lesson_and_textbook', context)]:
            if mode in result and result[mode].get('status') != 'error':
                continue
            drafts = result.setdefault('draft_needs', {})
            if mode not in drafts:
                drafts[mode] = await extract_needs(db, lesson, textbook=textbook)
                save()
            needs = drafts[mode]
            tasks = []
            for need in needs:
                for word in need['keywords']:
                    if word not in [query for _, query in tasks]:
                        tasks.append((need, word))
            tasks = tasks[:3]
            missing = [query for _, query in tasks if query not in search_cache]
            responses = await asyncio.gather(*(bocha_search(query) for query in missing), return_exceptions=True)
            failures = {}
            for query, response in zip(missing, responses):
                if isinstance(response, BaseException):
                    failures[query] = str(response) if isinstance(response, VideoSearchError) else '检索失败'
                else:
                    search_cache[query] = response
            save()
            candidates, seen, searches = [], set(), []
            for need, query in tasks:
                if query in failures:
                    searches.append(dict(query=query, error=failures[query]))
                    continue
                rows = search_cache[query]
                valid = normalize_candidates(rows, need)
                searches.append(dict(query=query, returned=len(rows), valid_videos=len(valid)))
                for item in valid:
                    if item['id'] not in seen:
                        seen.add(item['id'])
                        candidates.append(item)
            items = await rank_candidates(db, lesson.user_id,
                dict(title=lesson.title, subject=lesson.subject, grade=lesson.grade), needs, candidates)
            result[mode] = dict(needs=needs, searches=searches, candidates=candidates, items=items,
                status='error' if tasks and len(failures) == len(tasks) else 'ready' if items else 'no_results')
            save()
            print(json.dumps(dict(lesson_id=lesson.id, mode=mode, searches=searches,
                candidates=len(candidates), items=[dict(title=item['title'], url=item['url'], reason=item['reason'])
                    for item in items]), ensure_ascii=False), flush=True)


async def main(args):
    try:
        if not configured():
            raise ValueError('尚未配置视频搜索')
        for lesson_id in args.lesson_id:
            await compare(lesson_id, Path(args.output_dir))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lesson-id', type=int, action='append', required=True)
    parser.add_argument('--output-dir', required=True)
    try:
        asyncio.run(main(parser.parse_args()))
    except (VideoSearchError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
