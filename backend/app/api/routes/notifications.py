"""
通知管理路由
基于真实数据库的通知系统
支持通知的列表、已读、批量操作
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.notification import Notification

router = APIRouter()


class BatchReadRequest(BaseModel):
    ids: List[int]


async def ensure_welcome_notification(db: AsyncSession, user_id: int):
    """确保用户有欢迎通知（首次登录时自动创建）"""
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user_id)
    )
    count = result.scalar() or 0
    if count == 0:
        # 创建欢迎通知
        welcome = Notification(
            user_id=user_id,
            type="system",
            title="欢迎使用智慧试讲管理系统",
            content="您已成功登录系统。本系统搭载 AI 智能分析引擎，支持教案分析、视频多模态评估、备课助手等功能，助您提升教学能力。",
            link=None,
        )
        db.add(welcome)
        await db.commit()


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: Optional[str] = Query(None, description="通知类型过滤"),
    unread_only: bool = Query(False, description="仅显示未读"),
    is_read: Optional[bool] = Query(None, description="已读状态过滤"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取通知列表"""
    await ensure_welcome_notification(db, current_user.id)

    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(desc(Notification.created_at))
    )
    count_stmt = (
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id)
    )

    if type:
        stmt = stmt.where(Notification.type == type)
        count_stmt = count_stmt.where(Notification.type == type)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
        count_stmt = count_stmt.where(Notification.is_read == False)
    elif is_read is not None:
        stmt = stmt.where(Notification.is_read == is_read)
        count_stmt = count_stmt.where(Notification.is_read == is_read)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    notifications = list(result.scalars().all())

    items = [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "content": n.content,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else "",
            "link": n.link,
        }
        for n in notifications
    ]

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@router.get("/unread-count")
async def get_unread_count(
    type: Optional[str] = Query(None, description="通知类型过滤"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取未读通知数量"""
    conditions = [Notification.user_id == current_user.id, Notification.is_read.is_(False)]
    if type:
        conditions.append(Notification.type == type)
    result = await db.execute(
        select(func.count(Notification.id))
        .where(*conditions)
    )
    count = result.scalar() or 0
    return {"success": True, "data": {"count": count}}


@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """标记单个通知为已读"""
    await db.execute(
        update(Notification)
        .where(and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        ))
        .values(is_read=True)
    )
    await db.commit()
    return {"success": True, "message": "已标记为已读"}


@router.put("/batch-read")
async def batch_mark_as_read(
    request: BatchReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量标记通知为已读"""
    await db.execute(
        update(Notification)
        .where(and_(
            Notification.id.in_(request.ids),
            Notification.user_id == current_user.id
        ))
        .values(is_read=True)
    )
    await db.commit()
    return {"success": True, "message": f"已标记 {len(request.ids)} 条通知为已读"}


@router.put("/read-all")
async def mark_all_as_read(
    type: Optional[str] = Query(None, description="仅标记指定类型"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """标记所有通知为已读"""
    conditions = [Notification.user_id == current_user.id, Notification.is_read.is_(False)]
    if type:
        conditions.append(Notification.type == type)
    result = await db.execute(
        update(Notification)
        .where(*conditions)
        .values(is_read=True)
    )
    await db.commit()
    return {"success": True, "message": f"已标记所有通知为已读"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除通知"""
    await db.execute(
        delete(Notification)
        .where(and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        ))
    )
    await db.commit()
    return {"success": True, "message": "通知已删除"}


# ==================== 工具函数（供其他模块调用） ====================

async def create_notification(
    db: AsyncSession,
    user_id: int,
    type: str,
    title: str,
    content: str,
    link: Optional[str] = None,
    submission_id: Optional[int] = None,
):
    """创建一条通知（供其他模块调用）"""
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        content=content,
        link=link,
        submission_id=submission_id,
    )
    db.add(notification)
    await db.flush()
    return notification
