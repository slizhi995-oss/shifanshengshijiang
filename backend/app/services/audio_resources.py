"""Import supplied English audio and match it to saved, private lessons."""
import asyncio
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.audio_resource import AudioLesson, AudioResource, AudioVectorIndex
from app.models.textbook import Textbook, TextbookChapter, TextbookLesson
from app.services.audio_vectors import ALGORITHM, cosine, fit_idf, tokens, vectorize

MATCHING_VERSION = 'audio-match-v2-content-identity'


def audio_root():
    return (Path(settings.AUDIO_SOURCE_DIR) if settings.AUDIO_SOURCE_DIR else
            Path(__file__).resolve().parents[3] / '音频源文件').resolve()


def audio_path(relative):
    root = audio_root()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != '.mp3':
        raise ValueError('音频路径无效')
    return path


def file_digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_manifest():
    manifests = sorted(audio_root().glob('*/音频检索元数据.jsonl'))
    if len(manifests) != 1:
        raise ValueError('音频目录必须包含且仅包含一份“音频检索元数据.jsonl”')
    records = [json.loads(line) for line in manifests[0].read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if not records:
        raise ValueError('音频元数据为空，未修改已有索引')
    identifiers, paths = set(), set()
    prepared, failures = [], []
    for record in records:
        identifier, relative = record['resource_id'], record['relative_new']
        if not re.fullmatch(r'audio-[a-zA-Z0-9-]+', identifier) or identifier in identifiers or relative in paths:
            raise ValueError('音频元数据编号或相对路径重复/无效')
        identifiers.add(identifier)
        paths.add(relative)
        path = audio_path(relative)
        available = path.is_file() and file_digest(path) == record['sha256']
        if not available:
            failures.append(identifier)
        # Never persist old workstation paths or trust the old numeric textbook ID.
        metadata = {key: record.get(key) for key in (
            'publisher', 'activity_id', 'activity_description', 'lesson_number', 'textbook_excerpt',
            'location_status', 'audio_content_verified', 'note', 'match_basis', 'size_bytes')}
        search_text = record.get('search_text') or ' | '.join(str(record.get(key) or '') for key in (
            'subject', 'stage', 'series', 'volume', 'unit_title', 'section', 'audio_kind', 'textbook_excerpt'))
        prepared.append(dict(
            resource_id=identifier, relative_path=relative, sha256=record['sha256'],
            textbook_sha256=record['textbook_sha256'], subject=record.get('subject', '英语'),
            stage=record['stage'], series=record['series'], volume=record['volume'],
            unit_type=record['unit_type'], unit_number=record.get('unit_number'),
            unit_title=record['unit_title'], section=record.get('section') or '',
            audio_kind=record.get('audio_kind') or '', printed_page=record.get('printed_page'),
            pdf_page=record.get('pdf_page'), available=available,
            eligible=record.get('eligible_for_automatic_recommendation') is True,
            metadata_json=json.dumps(metadata, ensure_ascii=False), search_text=search_text))
    return prepared, failures


async def import_audio_catalog(db):
    prepared, failures = await asyncio.to_thread(read_manifest)
    existing = {row.resource_id: row for row in (await db.execute(select(AudioResource))).scalars()}
    documents = [item['search_text'] for item in prepared if item['available'] and item['eligible']]
    idf = await asyncio.to_thread(fit_idf, documents)
    version = hashlib.sha256((ALGORITHM + json.dumps(prepared, ensure_ascii=False, sort_keys=True)).encode()).hexdigest()
    for item in prepared:
        vector = vectorize(item['search_text'], idf) if item['available'] and item['eligible'] else {}
        item['vector_json'] = json.dumps(vector, ensure_ascii=False)
        row = existing.pop(item['resource_id'], None)
        if row is None:
            db.add(AudioResource(**item))
        else:
            for key, value in item.items():
                setattr(row, key, value)
    # Removed or corrupted files cannot remain recommendable after a reimport.
    for row in existing.values():
        row.available = False
        row.vector_json = '{}'
    index = await db.get(AudioVectorIndex, 1)
    if index is None:
        index = AudioVectorIndex(id=1, version=version, algorithm=ALGORITHM, idf_json='{}')
        db.add(index)
    index.version, index.algorithm, index.idf_json = version, ALGORITHM, json.dumps(idf, ensure_ascii=False)
    await db.flush()
    await backfill_audio_lessons(db)
    # Refresh all stored associations against the newly committed corpus version.
    for lesson in (await db.execute(select(AudioLesson))).scalars():
        await match_lesson_audio(db, lesson, force=True)
    await db.commit()
    return dict(total=len(prepared), indexed=len(documents), pending_review=sum(not item['eligible'] for item in prepared),
                unavailable=len(failures), failed_resources=failures, vocabulary=len(idf), version=version,
                algorithm=ALGORITHM)


def unit_key(text):
    match = re.search(r'\b(starter\s*unit|welcome\s*unit|unit|revision)\s*(\d+)?\b', text, re.I)
    if not match:
        return None
    kind = re.sub(r'\s+', '', match[1]).lower()
    return kind, int(match[2] or 0)


def resource_unit(resource):
    return re.sub(r'\s+', '', resource.unit_type).lower(), resource.unit_number or 0


def section_key(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def volume_key(text):
    """必修二 / 必修第二册 name the same volume, not two different editions."""
    label = unicodedata.normalize('NFKC', text or '')
    return re.sub(r'[\s第册]', '', label)


def unit_signature(text):
    label = text.split('·', 1)[0].strip()
    if re.search(r'\bworkbook\b', label, re.I):
        return None
    match = re.search(r'\b(starter\s*unit|welcome\s*unit|unit|revision)\s*(\d+)?\b(.*)', label, re.I)
    if not match:
        return None
    theme = re.sub(r'[^a-z0-9]', '', match[3].lower())
    key = unit_key(label)
    return (key, theme) if theme or key == ('welcomeunit', 0) else None


async def bound_catalog(db, source):
    """Prefer identical files; accept other PDF copies only with full unit evidence.

    A PDF hash identifies bytes, not a curriculum edition. Scans/OCR copies may
    differ while having the same volume and all the same named teaching units.
    Never fall back to volume or unit number alone.
    """
    query = select(AudioResource).where(AudioResource.eligible == True, AudioResource.available == True)
    exact = (await db.execute(query.where(AudioResource.textbook_sha256 == source['textbook_sha256']))).scalars().all()
    if exact:
        return exact, True
    book = (await db.execute(select(Textbook).where(Textbook.id == source.get('book_id'),
        Textbook.sha256 == source['textbook_sha256'], Textbook.subject == '英语'))).scalar_one_or_none()
    if book is None:
        return [], False
    stage = next((value for value in ('小学', '初中', '高中') if value in book.grade), None)
    if stage is None:
        return [], False
    chapters = (await db.execute(select(TextbookChapter).where(TextbookChapter.book_id == book.id,
        TextbookChapter.parent_title == ''))).scalars().all()
    signatures = {signature for chapter in chapters if (signature := unit_signature(chapter.title))}
    # At least three named units must agree, and every named unit must be covered.
    if len(signatures) < 3:
        return [], False
    groups = {}
    for item in (await db.execute(query.where(AudioResource.stage == stage))).scalars():
        if volume_key(item.volume) != volume_key(book.volume):
            continue
        # Explicit publisher/series disagreement must not be hidden by a match.
        if '北师大' in book.edition + book.publisher and '北师大' not in item.series:
            continue
        groups.setdefault(item.textbook_sha256, []).append(item)
    verified = []
    for items in groups.values():
        audio_signatures = {signature for item in items if (signature := unit_signature(item.unit_title))}
        if signatures <= audio_signatures:
            verified.append(items)
    # Ambiguous source copies need review instead of silently combining editions.
    return (verified[0], False) if len(verified) == 1 else ([], False)


def printed_page_numbers(label):
    pages = set()
    for match in re.finditer(r'(\d+)(?:\s*[-–—至]\s*(\d+))?', str(label or '')):
        first, last = int(match[1]), int(match[2] or match[1])
        if 0 <= last - first <= 100:
            pages.update(range(first, last + 1))
    return pages


def teaching_family(text):
    if re.search(r'\blistening\b', text, re.I):
        return 'listening'
    if re.search(r'\b(?:reading|writing)\b', text, re.I):
        return 'reading'
    if re.search(r'\bpronunciation\b', text, re.I):
        return 'pronunciation'
    return ''


async def match_lesson_audio(db, lesson, force=False):
    index = await db.get(AudioVectorIndex, 1)
    version = hashlib.sha256(json.dumps([
        MATCHING_VERSION, index.version if index else 'no-index', lesson.source_json,
        lesson.title, lesson.subject, lesson.grade, lesson.content,
    ], ensure_ascii=False).encode()).hexdigest()
    if not force and lesson.matched_version == version:
        return json.loads(lesson.matches_json)
    matches = []
    if lesson.subject != '英语':
        status = 'unsupported_subject'
    elif not index:
        status = 'index_empty'
    else:
        source = json.loads(lesson.source_json)
        query = select(AudioResource).where(AudioResource.eligible == True, AudioResource.available == True)
        bound = bool(source.get('textbook_sha256'))
        same_file = False
        if bound:
            candidates, same_file = await bound_catalog(db, source)
        else:
            stage = next((value for value in ('小学', '初中', '高中') if value in lesson.grade), None)
            if stage:
                query = query.where(AudioResource.stage == stage)
            year = re.search(r'[一二三四五六七八九]年级', lesson.grade)
            if year:
                query = query.where(AudioResource.volume.contains(year[0]))
            candidates = (await db.execute(query)).scalars().all()
        has_edition = bool(candidates)
        chapter_text = ' '.join(str(source.get(key) or '') for key in ('parent_title', 'chapter_title'))
        anchor = chapter_text if bound else lesson.title
        unit = unit_key(anchor)
        printed_pages = printed_page_numbers(source.get('printed_pages'))
        if unit:
            candidates = [item for item in candidates if resource_unit(item) == unit]
        elif bound:
            candidates = [item for item in candidates if (item.printed_page in printed_pages if printed_pages else
                          same_file and item.pdf_page is not None and
                          source.get('start_page', 0) <= item.pdf_page <= source.get('end_page', 0))]
        idf = json.loads(index.idf_json)
        query_text = ((lesson.title + ' ' + chapter_text + ' ') * 3 + lesson.content[:20000])
        query_vector = vectorize(query_text, idf)
        title_terms = set(tokens(lesson.title)) - {'unit', 'starter', 'welcome', '英语', '教案'}
        sections = section_key(chapter_text)
        family = teaching_family(chapter_text.split('·')[-1])
        lesson_number = re.search(r'\blesson\s*(\d+)\b', anchor, re.I)
        ranked = []
        for item in candidates:
            meta = json.loads(item.metadata_json)
            if lesson_number and meta.get('lesson_number') not in (None, int(lesson_number[1])):
                continue
            vocabulary = '词汇' in item.audio_kind
            item_family = teaching_family(item.section)
            if family and item_family and item_family != family and not vocabulary:
                continue
            score = cosine(query_vector, json.loads(item.vector_json))
            if not bound:
                # A generic lesson must name its topic, not merely mention listening.
                theme_terms = set(tokens(item.unit_title)) - {'unit', 'starter', 'welcome'}
                if len(title_terms & theme_terms) < min(2, len(theme_terms)) or not theme_terms or score < .18:
                    continue
            elif not unit and score < .05:
                continue
            on_page = item.printed_page in printed_pages if printed_pages else (
                same_file and item.pdf_page is not None and
                source.get('start_page', 0) <= item.pdf_page <= source.get('end_page', 0))
            same_section = bool(item.section and section_key(item.section) in sections)
            reason = ('对应教材页的配套音频' if on_page else
                      '同单元词汇音频，可用于词汇预习与复习' if item.audio_kind == '词汇' or '词汇' in item.audio_kind else
                      '同教材、同单元的配套音频' if bound else '课题与音频所属单元主题匹配')
            ranked.append((score + (.4 if on_page else 0) + (.15 if same_section else 0), item, score, reason))
        ranked.sort(key=lambda value: (-value[0], value[1].pdf_page or 9999, value[1].resource_id))
        matches = [dict(resource_id=item.resource_id, similarity=round(score, 4), reason=reason)
                   for _, item, score, reason in ranked[:12]]
        status = 'ready' if matches else 'edition_unavailable' if bound and not has_edition else 'no_match'
    lesson.matches_json = json.dumps(matches, ensure_ascii=False)
    lesson.matched_version, lesson.match_status = version, status
    return matches


async def save_audio_lesson(db, user_id, title, subject, grade, content, context=None, textbook_lesson_id=None):
    source = {key: context[key] for key in (
        'book_id', 'chapter_id', 'book_title', 'edition', 'volume', 'chapter_title', 'parent_title',
        'start_page', 'end_page', 'printed_pages', 'textbook_sha256') if context and key in context}
    lesson = AudioLesson(user_id=user_id, title=title[:180], subject=subject, grade=grade, content=content,
                         textbook_lesson_id=textbook_lesson_id, source_json=json.dumps(source, ensure_ascii=False))
    db.add(lesson)
    await db.flush()
    await match_lesson_audio(db, lesson)
    return lesson


async def backfill_audio_lessons(db, user_id=None):
    """Migrate saved textbook lessons without another generation or model call."""
    query = (select(TextbookLesson, TextbookChapter, Textbook)
             .outerjoin(TextbookChapter, TextbookLesson.chapter_id == TextbookChapter.id)
             .outerjoin(Textbook, TextbookChapter.book_id == Textbook.id)
             .outerjoin(AudioLesson, AudioLesson.textbook_lesson_id == TextbookLesson.id)
             .where(AudioLesson.id.is_(None)))
    if user_id is not None:
        query = query.where(TextbookLesson.user_id == user_id)
    for original, chapter, book in (await db.execute(query)).all():
        try:
            source = json.loads(original.sources_json)
            if not isinstance(source, dict):
                source = {}
        except (ValueError, TypeError):
            source = {}
        if book and chapter:
            source.update(book_id=book.id, chapter_id=chapter.id, textbook_sha256=book.sha256,
                          parent_title=chapter.parent_title, chapter_title=chapter.title,
                          start_page=chapter.start_page, end_page=chapter.end_page)
        lesson = await save_audio_lesson(db, original.user_id, original.title, book.subject if book else '',
                                       book.grade if book else '', original.content, source, original.id)
        lesson.created_at = original.created_at


async def owned_audio_lesson(db, user_id, lesson_id):
    lesson = (await db.execute(select(AudioLesson).where(
        AudioLesson.id == lesson_id, AudioLesson.user_id == user_id))).scalar_one_or_none()
    if not lesson:
        raise HTTPException(404, '教案资源不存在')
    return lesson


async def lesson_audio_items(db, lesson):
    matches = await match_lesson_audio(db, lesson)
    identifiers = [match['resource_id'] for match in matches]
    catalog = {item.resource_id: item for item in (await db.execute(select(AudioResource).where(
        AudioResource.resource_id.in_(identifiers), AudioResource.eligible == True,
        AudioResource.available == True))).scalars()} if identifiers else {}
    items = []
    for match in matches:
        item = catalog.get(match['resource_id'])
        if item is None:
            continue
        meta = json.loads(item.metadata_json)
        try:
            available = audio_path(item.relative_path).is_file()
        except ValueError:
            available = False
        items.append(dict(
            resource_id=item.resource_id, title=' · '.join(filter(None, (
                item.section, f'Lesson {meta["lesson_number"]}' if meta.get('lesson_number') else '',
                f'活动 {meta["activity_id"]}' if meta.get('activity_id') else '', item.audio_kind))),
            unit_title=item.unit_title, series=item.series, volume=item.volume, stage=item.stage,
            section=item.section, audio_kind=item.audio_kind, printed_page=item.printed_page,
            description=meta.get('activity_description') or '', textbook_excerpt=meta.get('textbook_excerpt') or '',
            audio_content_verified=bool(meta.get('audio_content_verified')), available=available,
            reason=match['reason'], size_bytes=meta.get('size_bytes') or 0))
    return items


async def matched_audio_file(db, user_id, lesson_id, resource_id):
    lesson = await owned_audio_lesson(db, user_id, lesson_id)
    matches = await match_lesson_audio(db, lesson)
    if resource_id not in {item['resource_id'] for item in matches}:
        raise HTTPException(404, '音频不属于这份教案')
    item = (await db.execute(select(AudioResource).where(AudioResource.resource_id == resource_id,
        AudioResource.available == True, AudioResource.eligible == True))).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, '音频不存在或暂不可用')
    try:
        path = audio_path(item.relative_path)
    except ValueError as exc:
        raise HTTPException(404, '音频不存在') from exc
    if not path.is_file():
        raise HTTPException(410, '音频文件已移除，请重新导入资源')
    if await asyncio.to_thread(file_digest, path) != item.sha256:
        raise HTTPException(409, '音频内容已改变，请重新核对并导入')
    return path
