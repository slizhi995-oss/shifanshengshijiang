"""Run the real chapter image pipeline and retain private diagnostic responses."""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from app.core.database import async_session_factory, engine
from app.models.textbook import TextbookLesson, Textbook, TextbookPage
from app.services.ai_model_service import DynamicAIService
from app.services.textbook_service import lesson_context, attach_lesson_images, private_path
from app.services.textbook_image_extraction import prepare_chapter_images, _page_figures_with_retry
from app.services.lesson_documents import create_word_document
from app.services.lesson_materials import markdown_asset_ids


async def main(chapter_id, generate=False, page=None):
    output = Path('outputs/image-recovery')/str(chapter_id)
    output.mkdir(parents=True, exist_ok=True)
    service = DynamicAIService()
    original = service.chat_completion
    sequence = 0
    async def record(**kwargs):
        nonlocal sequence
        sequence += 1
        index = sequence
        content = kwargs['messages'][-1]['content']
        page = json.loads(content[0]['text'])['pdf_page'] if isinstance(content,list) else 'lesson'
        response = await original(**kwargs)
        (output/f'{page}-{index}-{kwargs["usage_type"]}.txt').write_text(response, encoding='utf-8')
        return response
    service.chat_completion = record
    try:
        async with async_session_factory() as db:
            lesson = (await db.execute(select(TextbookLesson).where(TextbookLesson.chapter_id==chapter_id).order_by(TextbookLesson.id.desc()))).scalars().first()
            if not lesson:
                raise ValueError('Choose an existing lesson chapter for verification')
            context = await lesson_context(db, chapter_id, None, None)
            if page is not None:
                if not context['start_page']<=page<=context['end_page']:
                    raise ValueError('Page outside the confirmed chapter')
                book=await db.get(Textbook,context['book_id'])
                source_text=(await db.execute(select(TextbookPage.content).where(TextbookPage.book_id==book.id,TextbookPage.page_number==page))).scalar_one()
                figures=await _page_figures_with_retry(async_session_factory,service,lesson.user_id,None,
                    private_path(book.file_path),page,source_text,context,asyncio.Semaphore(1))
                for i,figure in enumerate(figures):
                    (output/f'verified-page-{page}-{i}.png').write_bytes(figure['raw'])
                print(json.dumps(dict(page=page,complete=figures.complete,figures=len(figures),issues=figures.issues),ensure_ascii=False))
                return
            result = await prepare_chapter_images(db.bind, service, lesson.user_id, context) if not generate else {'status':'verified_snapshot'}
            await db.commit()
            context = await lesson_context(db, chapter_id, None, None)
            result['assets'] = context['assets']
            (output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            if generate:
                raw = await service.generate_lesson_plan(db=db, user_id=lesson.user_id,
                    subject=context['subject'],grade=context['grade'],topic=context['chapter_title'],duration=15,
                    key_point='',difficulty='',template_type='default',template_text='',textbook_context=context)
                result = await attach_lesson_images(db,service,lesson.user_id,None,raw,context)
                result.update(await create_word_document(db,lesson.user_id,context['chapter_title'],result['content'],result['lesson_id']))
                (output/'generated-lesson.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                result = dict(lesson_id=result['lesson_id'],images=len(markdown_asset_ids(result['content'])),
                    placeholders=result['content'].count('图片待插入'),warnings=result['material_warnings'],document_id=result['document_id'])
            else:
                result['assets'] = [dict(id=asset['id'],title=asset['title'],figure_number=asset['figure_number']) for asset in result['assets']]
            print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        for client in service._clients.values():
            await client.close()
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chapter-id', type=int, required=True)
    parser.add_argument('--generate',action='store_true')
    parser.add_argument('--page',type=int)
    args=parser.parse_args()
    asyncio.run(main(args.chapter_id,args.generate,args.page))
