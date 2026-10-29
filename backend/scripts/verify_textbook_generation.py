"""Generate one real chapter-bound lesson with the configured text model.

Uses the actual database and records normal text-model usage. No AI image
generation is invoked. Outputs a Markdown lesson and portable image bundle.
"""
import argparse
import asyncio
import json
from pathlib import Path
from app.core.database import async_session_factory, engine
from app.services.ai_model_service import DynamicAIService
from app.services.textbook_service import lesson_context, attach_lesson_images, lesson_bundle
from app.models.textbook import TextbookLesson


async def main(chapter_id, user_id):
    api = DynamicAIService()
    destination = Path('outputs/textbook-generation')
    destination.mkdir(parents=True, exist_ok=True)
    try:
        calls = 0
        original_chat = api.chat_completion
        async def recording_chat(**kwargs):
            nonlocal calls
            calls += 1
            response = await original_chat(**kwargs)
            (destination / f'response-{calls}.txt').write_text(response, encoding='utf-8')
            return response
        api.chat_completion = recording_chat
        async with async_session_factory() as db:
            context = await lesson_context(db, chapter_id, '物理', '高中一年级')
            print(json.dumps({'stage': 'lesson', 'chapter_id': chapter_id}, ensure_ascii=True), flush=True)
            raw = await api.generate_lesson_plan(db=db, subject='物理', grade='高中一年级', topic=context['chapter_title'],
                duration=15, key_point='牛顿第一定律、惯性', difficulty='真实实验与理想实验的区别',
                template_type='default', template_text='', user_id=user_id, textbook_context=context)
            (destination / 'raw-lesson.md').write_text(raw, encoding='utf-8')
            print(json.dumps({'stage': 'images', 'characters': len(raw)}, ensure_ascii=True), flush=True)
            result = await attach_lesson_images(db, api, user_id, None, raw, context)
            (destination / '教案.md').write_text(result['content'], encoding='utf-8')
            lesson = await db.get(TextbookLesson, result['lesson_id'])
            (destination / '教案及图片.zip').write_bytes(await lesson_bundle(db, lesson))
            (destination / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'success': True, 'lesson_id': result['lesson_id'], 'images': len(result['asset_ids']),
                              'directory': str(destination)}, ensure_ascii=True), flush=True)
    finally:
        for client in api._clients.values():
            await client.close()
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chapter-id', type=int, required=True)
    parser.add_argument('--user-id', type=int, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.chapter_id, args.user_id))
