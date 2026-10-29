"""
Message-related Pydantic schemas.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class MessageCreate(BaseModel):
    """Schema for creating a message."""
    receiver_id: int = Field(..., description="接收者ID")
    content: str = Field(..., min_length=1, max_length=2000, description="消息内容")


class MessageResponse(BaseModel):
    """Message response schema."""
    id: int = Field(..., description="消息ID")
    sender_id: int = Field(..., description="发送者ID")
    receiver_id: int = Field(..., description="接收者ID")
    content: str = Field(..., description="消息内容")
    is_read: bool = Field(..., description="是否已读")
    created_at: datetime = Field(..., description="创建时间")
    
    # 关联信息
    sender: Optional[UserResponse] = Field(default=None, description="发送者信息")
    receiver: Optional[UserResponse] = Field(default=None, description="接收者信息")
    
    model_config = {"from_attributes": True}


class UnreadCount(BaseModel):
    """Unread message count."""
    count: int = Field(..., description="未读消息数量")
