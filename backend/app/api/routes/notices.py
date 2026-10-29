"""
Notice management API routes.
Handles system-wide announcements.
"""
import os
import uuid
import aiofiles
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.notice import Notice, NoticeRead, DisplayType
from app.schemas.notice import NoticeCreate, NoticeUpdate, NoticeResponse, NoticeWithReadStatus
from app.schemas.common import PageResult

router = APIRouter()

# 确保上传目录存在
NOTICE_UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "notices")
os.makedirs(NOTICE_UPLOAD_DIR, exist_ok=True)


@router.get(
    "/public/latest",
    response_model=Optional[NoticeResponse],
    summary="获取最新已发布通知（公开接口）",
)
async def get_latest_published_notice(
    semester_id: Optional[int] = Query(None, description="批次ID筛选"),
    db: AsyncSession = Depends(get_db),
) -> Optional[NoticeResponse]:
    query = select(Notice).where(Notice.is_published == True)
    if semester_id:
        query = query.where(
            (Notice.semester_id == semester_id) | (Notice.semester_id == None)
        )
    query = query.order_by(Notice.is_pinned.desc(), Notice.created_at.desc()).limit(1)

    result = await db.execute(query)
    notice = result.scalar_one_or_none()
    if not notice:
        return None
    return NoticeResponse.model_validate(notice)


@router.get(
    "/public/login",
    response_model=List[NoticeResponse],
    summary="获取登录页展示公告（公开接口）",
)
async def get_login_page_notices(
    db: AsyncSession = Depends(get_db),
) -> List[NoticeResponse]:
    """获取在登录页展示的公告列表（show_on_login=true且已发布）。"""
    query = (
        select(Notice)
        .where(Notice.is_published == True)
        .where(Notice.show_on_login == True)
        .order_by(Notice.is_pinned.desc(), Notice.created_at.desc())
        .limit(10)  # 最多返回10条
    )
    
    result = await db.execute(query)
    notices = result.scalars().all()
    
    return [NoticeResponse.model_validate(notice) for notice in notices]


@router.get(
    "",
    response_model=PageResult[NoticeResponse],
    summary="获取通知列表",
)
async def get_notices(
    semester_id: Optional[int] = Query(None, description="批次ID筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PageResult[NoticeResponse]:
    """
    获取通知列表。
    
    普通用户只能看到已发布的通知。
    管理员可以看到所有通知。
    """
    query = select(Notice)
    
    # 非管理员只能看已发布的
    if current_user.role.value != "admin":
        query = query.where(Notice.is_published == True)
    
    if semester_id:
        query = query.where(
            (Notice.semester_id == semester_id) | (Notice.semester_id == None)
        )
    
    # 置顶优先，然后按创建时间倒序
    query = query.order_by(Notice.is_pinned.desc(), Notice.created_at.desc())
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    notices = result.scalars().all()
    
    return PageResult.create(
        items=[NoticeResponse.model_validate(n) for n in notices],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/user/unread-count",
    summary="获取未读公告数量",
)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取当前用户的未读公告数量。"""
    # 获取所有已发布的公告ID
    published_query = select(Notice.id).where(Notice.is_published == True)
    published_result = await db.execute(published_query)
    published_ids = set(r[0] for r in published_result.fetchall())
    
    # 获取用户已读的公告ID
    read_query = select(NoticeRead.notice_id).where(NoticeRead.user_id == current_user.id)
    read_result = await db.execute(read_query)
    read_ids = set(r[0] for r in read_result.fetchall())
    
    # 计算未读数量
    unread_count = len(published_ids - read_ids)
    
    return {"unread_count": unread_count}


@router.get(
    "/user/list",
    response_model=PageResult[NoticeWithReadStatus],
    summary="获取用户公告列表（带已读状态）",
)
async def get_user_notices(
    is_read: Optional[bool] = Query(None, description="筛选已读/未读"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PageResult[NoticeWithReadStatus]:
    """获取用户公告列表，包含已读状态，支持筛选。"""
    # 获取用户已读的公告ID
    read_query = select(NoticeRead.notice_id).where(NoticeRead.user_id == current_user.id)
    read_result = await db.execute(read_query)
    read_ids = set(r[0] for r in read_result.fetchall())
    
    # 查询已发布的公告
    query = select(Notice).where(Notice.is_published == True)
    query = query.order_by(Notice.is_pinned.desc(), Notice.created_at.desc())
    
    # 获取所有公告先
    all_result = await db.execute(query)
    all_notices = all_result.scalars().all()
    
    # 根据已读状态筛选
    if is_read is not None:
        if is_read:
            filtered_notices = [n for n in all_notices if n.id in read_ids]
        else:
            filtered_notices = [n for n in all_notices if n.id not in read_ids]
    else:
        filtered_notices = list(all_notices)
    
    total = len(filtered_notices)
    
    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    paged_notices = filtered_notices[start:end]
    
    # 构建响应
    items = [
        NoticeWithReadStatus.from_notice(n, is_read=n.id in read_ids)
        for n in paged_notices
    ]
    
    return PageResult.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/user/read/{notice_id}",
    summary="标记公告为已读",
)
async def mark_notice_read(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """标记指定公告为已读。"""
    # 检查公告是否存在
    notice = await db.get(Notice, notice_id)
    if not notice or not notice.is_published:
        raise HTTPException(status_code=404, detail="公告不存在")
    
    # 检查是否已读
    existing = await db.execute(
        select(NoticeRead).where(
            NoticeRead.user_id == current_user.id,
            NoticeRead.notice_id == notice_id
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "已标记为已读"}
    
    # 创建已读记录
    read_record = NoticeRead(user_id=current_user.id, notice_id=notice_id)
    db.add(read_record)
    await db.commit()
    
    return {"message": "标记成功"}


@router.post(
    "/user/read-all",
    summary="标记所有公告为已读",
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """标记所有公告为已读。"""
    # 获取所有已发布的公告ID
    published_query = select(Notice.id).where(Notice.is_published == True)
    published_result = await db.execute(published_query)
    published_ids = [r[0] for r in published_result.fetchall()]
    
    # 获取用户已读的公告ID
    read_query = select(NoticeRead.notice_id).where(NoticeRead.user_id == current_user.id)
    read_result = await db.execute(read_query)
    read_ids = set(r[0] for r in read_result.fetchall())
    
    # 创建未读公告的已读记录
    for notice_id in published_ids:
        if notice_id not in read_ids:
            read_record = NoticeRead(user_id=current_user.id, notice_id=notice_id)
            db.add(read_record)
    
    await db.commit()
    
    return {"message": "已全部标记为已读"}


@router.get(
    "/admin/read-stats",
    summary="获取所有公告的已读统计（管理员）",
)
async def get_read_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """获取所有公告的已读人数统计。"""
    # 统计每个公告的已读人数
    stats_query = select(
        NoticeRead.notice_id,
        func.count(NoticeRead.id).label('read_count')
    ).group_by(NoticeRead.notice_id)
    
    result = await db.execute(stats_query)
    stats = {row[0]: row[1] for row in result.fetchall()}
    
    return {"read_stats": stats}


@router.post(
    "",
    response_model=NoticeResponse,
    summary="发布通知",
)
async def create_notice(
    notice_data: NoticeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> NoticeResponse:
    """管理员发布新通知。"""
    notice = Notice(
        title=notice_data.title,
        content=notice_data.content,
        semester_id=notice_data.semester_id,
        is_pinned=notice_data.is_pinned,
        is_published=notice_data.is_published,
        display_type=DisplayType(notice_data.display_type.value),
        attachment_path=notice_data.attachment_path,
    )
    
    db.add(notice)
    await db.commit()
    await db.refresh(notice)
    
    return NoticeResponse.model_validate(notice)


@router.get(
    "/{notice_id}",
    response_model=NoticeResponse,
    summary="获取通知详情",
)
async def get_notice(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoticeResponse:
    """获取单个通知的详细信息。"""
    notice = await db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    # 非管理员不能看未发布的通知
    if current_user.role.value != "admin" and not notice.is_published:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    return NoticeResponse.model_validate(notice)


@router.put(
    "/{notice_id}",
    response_model=NoticeResponse,
    summary="更新通知",
)
async def update_notice(
    notice_id: int,
    notice_data: NoticeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> NoticeResponse:
    """更新通知信息。"""
    notice = await db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    update_data = notice_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "display_type" and value:
            value = DisplayType(value)
        setattr(notice, field, value)
    
    await db.commit()
    await db.refresh(notice)
    
    return NoticeResponse.model_validate(notice)


@router.delete(
    "/{notice_id}",
    summary="删除通知",
)
async def delete_notice(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """删除通知。"""
    notice = await db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(status_code=404, detail="通知不存在")
    
    await db.delete(notice)
    await db.commit()
    
    return {"message": "通知已删除"}


@router.post(
    "/upload/image",
    summary="上传公告图片",
)
async def upload_notice_image(
    file: UploadFile = File(..., description="图片文件"),
    _: User = Depends(require_admin),
) -> dict:
    """
    上传公告图片，用于富文本编辑器。
    支持格式: jpg, jpeg, png, gif, webp
    """
    # 验证文件类型
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    file_ext = os.path.splitext(file.filename or '')[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式，请上传 {', '.join(allowed_extensions)}"
        )
    
    # 生成唯一文件名
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(NOTICE_UPLOAD_DIR, unique_name)
    
    # 保存文件
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # 返回访问URL
    return {
        "url": f"/api/v1/notices/files/{unique_name}",
        "alt": file.filename,
    }


@router.post(
    "/upload/attachment",
    summary="上传公告附件",
)
async def upload_notice_attachment(
    file: UploadFile = File(..., description="附件文件"),
    _: User = Depends(require_admin),
) -> dict:
    """
    上传公告附件。
    支持格式: pdf, doc, docx, xls, xlsx, ppt, pptx, zip, rar
    """
    # 验证文件类型
    allowed_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar'}
    file_ext = os.path.splitext(file.filename or '')[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的附件格式，请上传 {', '.join(allowed_extensions)}"
        )
    
    # 生成唯一文件名（保留原始文件名信息）
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(NOTICE_UPLOAD_DIR, unique_name)
    
    # 保存文件
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    return {
        "url": f"/api/v1/notices/files/{unique_name}",
        "name": file.filename,
        "size": len(content),
    }


@router.get(
    "/files/{filename}",
    summary="获取公告文件",
)
async def get_notice_file(filename: str):
    """获取公告上传的文件（图片/附件）。"""
    file_path = os.path.join(NOTICE_UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(file_path)
