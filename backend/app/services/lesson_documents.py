"""Private, owner-scoped Word documents for generated and historical lessons."""
import asyncio
import json
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import select

from app.models.textbook import TextbookLesson
from app.services.lesson_materials import markdown_asset_ids
from app.services.lesson_word import build_lesson_docx, safe_filename
from app.services.textbook_service import private_path, textbook_image_path
from app.services.lesson_content import clean_lesson_content

DOCUMENT_VERSION=2


async def _render_document(db,user_id,title,content,lesson_id=None):
    images={}
    if lesson_id:
        lesson=(await db.execute(select(TextbookLesson).where(TextbookLesson.id==lesson_id,TextbookLesson.user_id==user_id))).scalar_one_or_none()
        if not lesson:raise HTTPException(404,'教案不存在')
        content=lesson.content
        content=clean_lesson_content(content)
        for identifier in markdown_asset_ids(content):
            try:
                path,_=await textbook_image_path(db,identifier)
                images[identifier]=path
            except ValueError as exc:
                raise HTTPException(409,'教案图片缺失或已改变，请管理员核对') from exc
    if not content.strip():raise HTTPException(422,'教案内容为空')
    return await asyncio.to_thread(build_lesson_docx,content,title,images)


async def create_word_document(db,user_id,title,content,lesson_id=None):
    data=await _render_document(db,user_id,title,content,lesson_id)
    identifier=uuid.uuid4().hex
    path=private_path(f'word-documents/{user_id}/{identifier}.docx')
    path.parent.mkdir(parents=True,exist_ok=True)
    await asyncio.to_thread(path.write_bytes,data)
    metadata=dict(filename=safe_filename(title),lesson_id=lesson_id,title=title,version=DOCUMENT_VERSION)
    if not lesson_id:metadata['content']=content
    await asyncio.to_thread(path.with_suffix('.json').write_text,json.dumps(metadata,ensure_ascii=False),encoding='utf-8')
    return dict(document_id=identifier,document_format='docx',document_filename=metadata['filename'])


async def word_document(db,user_id,identifier):
    if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise HTTPException(404,'Word文档不存在')
    path=private_path(f'word-documents/{user_id}/{identifier}.docx')
    if not path.is_file() or not path.with_suffix('.json').is_file():raise HTTPException(404,'Word文档不存在')
    metadata=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if metadata.get('version')!=DOCUMENT_VERSION:
        lesson_id=metadata.get('lesson_id')
        if not lesson_id and not metadata.get('content'):
            # The browser still has the original local history and can request
            # a conversion when an old general document lacks stored source.
            raise HTTPException(404,'旧教案需要重新排版')
        title=metadata.get('title') or metadata['filename'].removesuffix('.docx')
        data=await _render_document(db,user_id,title,metadata.get('content',''),lesson_id)
        temporary=path.with_suffix('.tmp-'+uuid.uuid4().hex)
        await asyncio.to_thread(temporary.write_bytes,data)
        await asyncio.to_thread(temporary.replace,path)
        metadata['version']=DOCUMENT_VERSION
        await asyncio.to_thread(path.with_suffix('.json').write_text,json.dumps(metadata,ensure_ascii=False),encoding='utf-8')
    return path,metadata['filename']
