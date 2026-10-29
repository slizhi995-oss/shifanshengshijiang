"""
Message API routes.
Handles student-instructor communication.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageResponse, UnreadCount
from app.schemas.common import PageResult

router = APIRouter()


@router.get(
    "/conversation/{user_id}",
    response_model=List[MessageResponse],
    summary="获取与某用户的对话",
)
async def get_conversation(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[MessageResponse]:
    """
    获取当前用户与指定用户之间的消息历史。
    
    按时间正序排列，支持分页。
    """
    query = (
        select(Message)
        .where(
            or_(
                and_(
                    Message.sender_id == current_user.id,
                    Message.receiver_id == user_id,
                ),
                and_(
                    Message.sender_id == user_id,
                    Message.receiver_id == current_user.id,
                ),
            )
        )
        .options(
            selectinload(Message.sender),
            selectinload(Message.receiver),
        )
        .order_by(Message.created_at.asc())
    )
    
    # 分页 - 获取最近的消息
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # 标记接收的消息为已读
    for msg in messages:
        if msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
    await db.commit()
    
    return [MessageResponse.model_validate(m) for m in messages]


@router.post(
    "",
    response_model=MessageResponse,
    summary="发送消息",
)
async def send_message(
    message_data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """发送消息给指定用户。"""
    # 验证接收者存在
    receiver = await db.get(User, message_data.receiver_id)
    if not receiver:
        raise HTTPException(status_code=404, detail="接收者不存在")
    
    if not receiver.is_active:
        raise HTTPException(status_code=400, detail="接收者账号已禁用")
    
    if message_data.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能给自己发消息")
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=message_data.receiver_id,
        content=message_data.content,
        is_read=False,
    )
    
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    # 加载关联
    await db.refresh(message, ["sender", "receiver"])
    
    return MessageResponse.model_validate(message)


@router.get(
    "/unread-count",
    response_model=UnreadCount,
    summary="获取未读消息数",
)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadCount:
    """获取当前用户的未读消息总数。"""
    result = await db.execute(
        select(func.count()).where(
            Message.receiver_id == current_user.id,
            Message.is_read == False,
        )
    )
    count = result.scalar() or 0
    
    return UnreadCount(count=count)


@router.get(
    "/contacts",
    response_model=List[dict],
    summary="获取联系人列表",
)
async def get_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[dict]:
    """
    获取有过消息往来的联系人列表。
    
    返回联系人信息和最后一条消息、未读数。
    """
    # 获取所有相关的消息
    messages_result = await db.execute(
        select(Message)
        .where(
            or_(
                Message.sender_id == current_user.id,
                Message.receiver_id == current_user.id,
            )
        )
        .options(
            selectinload(Message.sender),
            selectinload(Message.receiver),
        )
        .order_by(Message.created_at.desc())
    )
    messages = messages_result.scalars().all()
    
    # 按联系人分组
    contacts_map = {}
    for msg in messages:
        # 确定对方是谁
        other_user = msg.receiver if msg.sender_id == current_user.id else msg.sender
        other_id = other_user.id
        
        if other_id not in contacts_map:
            contacts_map[other_id] = {
                "user": {
                    "id": other_user.id,
                    "name": other_user.name,
                    "user_code": other_user.user_code,
                    "role": other_user.role.value,
                    "avatar": other_user.avatar,
                },
                "last_message": {
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "is_mine": msg.sender_id == current_user.id,
                },
                "unread_count": 0,
            }
        
        # 统计未读
        if msg.receiver_id == current_user.id and not msg.is_read:
            contacts_map[other_id]["unread_count"] += 1
    
    return list(contacts_map.values())


@router.post(
    "/mark-read/{user_id}",
    summary="标记与某用户的消息为已读",
)
async def mark_messages_read(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """将来自指定用户的所有消息标记为已读。"""
    result = await db.execute(
        select(Message).where(
            Message.sender_id == user_id,
            Message.receiver_id == current_user.id,
            Message.is_read == False,
        )
    )
    messages = result.scalars().all()
    
    for msg in messages:
        msg.is_read = True
    
    await db.commit()
    
    return {"marked_count": len(messages)}
