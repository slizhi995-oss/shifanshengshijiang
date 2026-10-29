"""
Notice-related Pydantic schemas.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DisplayTypeEnum(str, Enum):
    """公告显示类型"""
    DIALOG = "dialog"       # 弹窗
    MARQUEE = "marquee"     # 跑马灯
    BOTH = "both"           # 两者都有


class NoticeBase(BaseModel):
    """Base notice schema."""
    title: str = Field(..., min_length=1, max_length=256, description="通知标题")
    content: str = Field(..., min_length=1, description="通知内容")
    semester_id: Optional[int] = Field(default=None, description="关联批次ID")
    is_pinned: bool = Field(default=False, description="是否置顶")
    display_type: DisplayTypeEnum = Field(default=DisplayTypeEnum.DIALOG, description="显示类型")


class NoticeCreate(NoticeBase):
    """Schema for creating a notice."""
    is_published: bool = Field(default=True, description="是否发布")
    show_on_login: bool = Field(default=False, description="是否在登录页展示")
    attachment_path: Optional[str] = Field(default=None, description="附件路径JSON")


class NoticeUpdate(BaseModel):
    """Schema for updating a notice."""
    title: Optional[str] = Field(default=None, max_length=256, description="通知标题")
    content: Optional[str] = Field(default=None, description="通知内容")
    semester_id: Optional[int] = Field(default=None, description="关联批次ID")
    is_pinned: Optional[bool] = Field(default=None, description="是否置顶")
    is_published: Optional[bool] = Field(default=None, description="是否发布")
    show_on_login: Optional[bool] = Field(default=None, description="是否在登录页展示")
    display_type: Optional[DisplayTypeEnum] = Field(default=None, description="显示类型")
    attachment_path: Optional[str] = Field(default=None, description="附件路径JSON")


class NoticeResponse(BaseModel):
    """Notice response schema."""
    id: int = Field(..., description="通知ID")
    title: str = Field(..., description="通知标题")
    content: str = Field(..., description="通知内容")
    semester_id: Optional[int] = Field(default=None, description="关联批次ID")
    is_pinned: bool = Field(..., description="是否置顶")
    is_published: bool = Field(..., description="是否发布")
    show_on_login: bool = Field(default=False, description="是否在登录页展示")
    display_type: str = Field(..., description="显示类型")
    attachment_path: Optional[str] = Field(default=None, description="附件路径")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = {"from_attributes": True}
    
    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Custom validation to handle enum conversion."""
        # Get display_type value, default to 'dialog' if None
        display_type_value = 'dialog'
        if hasattr(obj, 'display_type') and obj.display_type is not None:
            if hasattr(obj.display_type, 'value'):
                display_type_value = obj.display_type.value
            else:
                display_type_value = str(obj.display_type)
        
        # Create a dict from the object
        data = {
            'id': obj.id,
            'title': obj.title,
            'content': obj.content,
            'semester_id': obj.semester_id,
            'is_pinned': obj.is_pinned,
            'is_published': obj.is_published,
            'show_on_login': getattr(obj, 'show_on_login', False),
            'display_type': display_type_value,
            'attachment_path': obj.attachment_path,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
        }
        return cls(**data)


class NoticeWithReadStatus(NoticeResponse):
    """Notice response with read status."""
    is_read: bool = Field(default=False, description="是否已读")
    
    @classmethod
    def from_notice(cls, notice, is_read: bool = False):
        """Create from Notice object with read status."""
        display_type_value = 'dialog'
        if hasattr(notice, 'display_type') and notice.display_type is not None:
            if hasattr(notice.display_type, 'value'):
                display_type_value = notice.display_type.value
            else:
                display_type_value = str(notice.display_type)
        
        return cls(
            id=notice.id,
            title=notice.title,
            content=notice.content,
            semester_id=notice.semester_id,
            is_pinned=notice.is_pinned,
            is_published=notice.is_published,
            show_on_login=getattr(notice, 'show_on_login', False),
            display_type=display_type_value,
            attachment_path=notice.attachment_path,
            created_at=notice.created_at,
            updated_at=notice.updated_at,
            is_read=is_read,
        )
