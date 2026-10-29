"""
聊天功能API
支持师生之间的即时通讯，按批次分组联系人
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.message import Message
from app.models.group import Group
from app.models.semester import Semester
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter()


# ==================== Schemas ====================

class MessageSend(BaseModel):
    """发送消息请求"""
    receiver_id: int = Field(..., description="接收者ID")
    content: str = Field(..., min_length=1, description="消息内容")
    semester_id: Optional[int] = Field(None, description="批次ID")


class MessageResponse(BaseModel):
    """消息响应"""
    id: int
    sender_id: int
    receiver_id: int
    sender_name: str
    receiver_name: str
    content: str
    is_read: bool
    semester_id: Optional[int]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ContactResponse(BaseModel):
    """联系人响应"""
    user_id: int
    user_name: str
    user_code: str
    role: str
    college: Optional[str] = None
    major: Optional[str] = None
    class_name: Optional[str] = None
    semester_id: Optional[int]
    semester_name: Optional[str]
    last_message: Optional[str]
    last_message_time: Optional[datetime]
    unread_count: int


# ==================== API Endpoints ====================

@router.get(
    "/contacts",
    summary="获取联系人列表",
)
async def get_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ContactResponse]:
    """
    获取联系人列表，按批次分组
    
    权限说明：
    - 学生：只能看到自己的指导老师
    - 指导老师：只能看到自己分配到的学生
    """
    contacts = []
    
    if current_user.role == UserRole.STUDENT:
        # 学生获取自己所有批次的指导老师
        groups_result = await db.execute(
            select(Group).where(
                Group.student_id == current_user.id
            ).options(
                selectinload(Group.instructor),
                selectinload(Group.semester)
            )
        )
        groups = groups_result.scalars().all()
        
        for group in groups:
            if not group.instructor:
                continue
                
            # 获取最后一条消息
            last_msg_result = await db.execute(
                select(Message).where(
                    or_(
                        and_(
                            Message.sender_id == current_user.id,
                            Message.receiver_id == group.instructor.id
                        ),
                        and_(
                            Message.sender_id == group.instructor.id,
                            Message.receiver_id == current_user.id
                        )
                    )
                ).order_by(desc(Message.created_at)).limit(1)
            )
            last_msg = last_msg_result.scalar_one_or_none()
            
            # 获取未读消息数
            unread_result = await db.execute(
                select(func.count()).select_from(Message).where(
                    Message.sender_id == group.instructor.id,
                    Message.receiver_id == current_user.id,
                    Message.is_read == False
                )
            )
            unread_count = unread_result.scalar() or 0
            
            contacts.append(ContactResponse(
                user_id=group.instructor.id,
                user_name=group.instructor.name,
                user_code=group.instructor.user_code,
                role="instructor",
                college=group.instructor.college,
                major=None,
                class_name=None,
                semester_id=group.semester_id,
                semester_name=group.semester.name if group.semester else None,
                last_message=last_msg.content if last_msg else None,
                last_message_time=last_msg.created_at if last_msg else None,
                unread_count=unread_count
            ))
    
    elif current_user.role == UserRole.INSTRUCTOR:
        # 指导老师获取自己所有批次分配到的学生
        groups_result = await db.execute(
            select(Group).where(
                Group.instructor_id == current_user.id
            ).options(
                selectinload(Group.student),
                selectinload(Group.semester)
            )
        )
        groups = groups_result.scalars().all()
        
        for group in groups:
            if not group.student:
                continue
                
            # 获取最后一条消息
            last_msg_result = await db.execute(
                select(Message).where(
                    or_(
                        and_(
                            Message.sender_id == current_user.id,
                            Message.receiver_id == group.student.id
                        ),
                        and_(
                            Message.sender_id == group.student.id,
                            Message.receiver_id == current_user.id
                        )
                    )
                ).order_by(desc(Message.created_at)).limit(1)
            )
            last_msg = last_msg_result.scalar_one_or_none()
            
            # 获取未读消息数
            unread_result = await db.execute(
                select(func.count()).select_from(Message).where(
                    Message.sender_id == group.student.id,
                    Message.receiver_id == current_user.id,
                    Message.is_read == False
                )
            )
            unread_count = unread_result.scalar() or 0
            
            contacts.append(ContactResponse(
                user_id=group.student.id,
                user_name=group.student.name,
                user_code=group.student.user_code,
                role="student",
                college=group.student.college,
                major=group.student.major,
                class_name=group.student.class_name,
                semester_id=group.semester_id,
                semester_name=group.semester.name if group.semester else None,
                last_message=last_msg.content if last_msg else None,
                last_message_time=last_msg.created_at if last_msg else None,
                unread_count=unread_count
            ))
    
    # 按批次和最后消息时间排序
    contacts.sort(key=lambda x: (
        x.semester_id or 0,
        x.last_message_time or datetime.min
    ), reverse=True)
    
    return contacts


@router.get(
    "/conversations/{user_id}",
    summary="获取与某人的聊天记录",
)
async def get_conversation(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取与指定用户的聊天记录
    
    权限验证：
    - 学生只能查看与自己导师的聊天
    - 导师只能查看与自己学生的聊天
    """
    # 获取对方用户信息
    other_user = await db.get(User, user_id)
    if not other_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 权限验证
    if current_user.role == UserRole.STUDENT:
        # 验证是否是自己的导师（可能在多个批次有关系）
        group_result = await db.execute(
            select(Group).where(
                Group.student_id == current_user.id,
                Group.instructor_id == user_id
            ).limit(1)
        )
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="您只能联系自己的指导老师")
    
    elif current_user.role == UserRole.INSTRUCTOR:
        # 验证是否是自己的学生（可能在多个批次有关系）
        group_result = await db.execute(
            select(Group).where(
                Group.instructor_id == current_user.id,
                Group.student_id == user_id
            ).limit(1)
        )
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="您只能联系自己指导的学生")
    
    # 获取聊天记录
    messages_query = (
        select(Message)
        .where(
            or_(
                and_(
                    Message.sender_id == current_user.id,
                    Message.receiver_id == user_id
                ),
                and_(
                    Message.sender_id == user_id,
                    Message.receiver_id == current_user.id
                )
            )
        )
        .order_by(desc(Message.created_at))
    )
    
    # 获取总数
    count_result = await db.execute(
        select(func.count()).select_from(messages_query.subquery())
    )
    total = count_result.scalar() or 0
    
    # 分页
    messages_query = messages_query.offset((page - 1) * page_size).limit(page_size)
    messages_result = await db.execute(
        messages_query.options(
            selectinload(Message.sender),
            selectinload(Message.receiver)
        )
    )
    messages = messages_result.scalars().all()
    
    # 标记收到的消息为已读
    await db.execute(
        update(Message)
        .where(
            and_(
                Message.sender_id == user_id,
                Message.receiver_id == current_user.id,
                Message.is_read == False
            )
        )
        .values(is_read=True)
    )
    await db.commit()
    
    # 构建响应
    message_list = []
    for msg in reversed(messages):  # 反转顺序，最早的在前
        message_list.append(MessageResponse(
            id=msg.id,
            sender_id=msg.sender_id,
            receiver_id=msg.receiver_id,
            sender_name=msg.sender.name,
            receiver_name=msg.receiver.name,
            content=msg.content,
            is_read=msg.is_read,
            semester_id=msg.semester_id,
            created_at=msg.created_at
        ))
    
    return {
        "messages": message_list,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.post(
    "/send",
    summary="发送消息",
)
async def send_message(
    msg_data: MessageSend,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    发送消息给指定用户
    
    权限验证：
    - 学生只能给自己的导师发消息
    - 导师只能给自己的学生发消息
    """
    # 获取接收者
    receiver = await db.get(User, msg_data.receiver_id)
    if not receiver:
        raise HTTPException(status_code=404, detail="接收者不存在")
    
    # 权限验证
    if current_user.role == UserRole.STUDENT:
        # 验证是否是自己的导师（可能在多个批次有关系）
        group_result = await db.execute(
            select(Group).where(
                Group.student_id == current_user.id,
                Group.instructor_id == msg_data.receiver_id
            ).limit(1)
        )
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="您只能给自己的指导老师发消息")
    
    elif current_user.role == UserRole.INSTRUCTOR:
        # 验证是否是自己的学生（可能在多个批次有关系）
        group_result = await db.execute(
            select(Group).where(
                Group.instructor_id == current_user.id,
                Group.student_id == msg_data.receiver_id
            ).limit(1)
        )
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="您只能给自己指导的学生发消息")
    
    # 创建消息
    new_message = Message(
        sender_id=current_user.id,
        receiver_id=msg_data.receiver_id,
        content=msg_data.content,
        semester_id=msg_data.semester_id,
        is_read=False
    )
    
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    
    # 加载关系
    await db.refresh(new_message, ["sender", "receiver"])
    
    return MessageResponse(
        id=new_message.id,
        sender_id=new_message.sender_id,
        receiver_id=new_message.receiver_id,
        sender_name=new_message.sender.name,
        receiver_name=new_message.receiver.name,
        content=new_message.content,
        is_read=new_message.is_read,
        semester_id=new_message.semester_id,
        created_at=new_message.created_at
    )


@router.get(
    "/unread-count",
    summary="获取未读消息总数",
)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取当前用户的未读消息总数"""
    result = await db.execute(
        select(func.count()).select_from(Message).where(
            Message.receiver_id == current_user.id,
            Message.is_read == False
        )
    )
    count = result.scalar() or 0
    
    return {"unread_count": count}


@router.put(
    "/{message_id}/read",
    summary="标记消息为已读",
)
async def mark_as_read(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """标记指定消息为已读"""
    message = await db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    
    if message.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="您不能标记他人的消息")
    
    message.is_read = True
    await db.commit()
    
    return {"message": "已标记为已读"}
