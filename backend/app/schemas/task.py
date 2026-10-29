"""
Task-related Pydantic schemas.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class TaskBase(BaseModel):
    """Base task schema."""
    title: str = Field(..., min_length=1, max_length=256, description="任务标题")
    content: str = Field(..., min_length=1, description="任务内容(富文本)")
    deadline: Optional[datetime] = Field(default=None, description="截止日期")
    require_lesson_plan: bool = Field(default=True, description="是否要求上传教案")
    require_video: bool = Field(default=True, description="是否要求上传视频")


class TaskCreate(TaskBase):
    """Schema for creating a task."""
    semester_id: int = Field(..., description="批次ID")
    is_published: bool = Field(default=False, description="是否立即发布")


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    title: Optional[str] = Field(default=None, max_length=256, description="任务标题")
    content: Optional[str] = Field(default=None, description="任务内容")
    deadline: Optional[datetime] = Field(default=None, description="截止日期")
    require_lesson_plan: Optional[bool] = Field(default=None, description="是否要求上传教案")
    require_video: Optional[bool] = Field(default=None, description="是否要求上传视频")
    is_published: Optional[bool] = Field(default=None, description="是否发布")


class TaskResponse(BaseModel):
    """Task response schema."""
    id: int = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    content: str = Field(..., description="任务内容")
    semester_id: int = Field(..., description="批次ID")
    instructor_id: int = Field(..., description="发布老师ID")
    deadline: Optional[datetime] = Field(default=None, description="截止日期")
    require_lesson_plan: bool = Field(..., description="是否要求上传教案")
    require_video: bool = Field(..., description="是否要求上传视频")
    is_published: bool = Field(..., description="是否已发布")
    attachment_path: Optional[str] = Field(default=None, description="附件路径")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 关联信息
    instructor: Optional[UserResponse] = Field(default=None, description="发布老师信息")
    
    # 统计信息
    submission_count: Optional[int] = Field(default=None, description="提交数量")
    pending_count: Optional[int] = Field(default=None, description="待审核数量")
    approved_count: Optional[int] = Field(default=None, description="已通过数量")
    rejected_count: Optional[int] = Field(default=None, description="已驳回数量")
    
    model_config = {"from_attributes": True}
