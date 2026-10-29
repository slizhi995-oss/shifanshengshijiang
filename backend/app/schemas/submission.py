"""
Submission-related Pydantic schemas.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.submission import SubmissionStatus
from app.schemas.user import UserResponse
from app.schemas.task import TaskResponse


class SubmissionCreate(BaseModel):
    """Schema for creating/updating a submission."""
    task_id: int = Field(..., description="任务ID")
    student_remark: Optional[str] = Field(default=None, description="学生备注")


class SubmissionUpdate(BaseModel):
    """Schema for updating submission files."""
    student_remark: Optional[str] = Field(default=None, description="学生备注")


class SubmissionReview(BaseModel):
    """Schema for instructor reviewing a submission."""
    lesson_plan_score: Optional[float] = Field(default=None, ge=0, le=100, description="教案分数")
    video_score: Optional[float] = Field(default=None, ge=0, le=100, description="视频分数")
    total_score: float = Field(..., ge=0, le=100, description="总分")
    feedback: Optional[str] = Field(default=None, description="评语")
    
    @field_validator("total_score")
    @classmethod
    def validate_total_score(cls, v: float) -> float:
        return round(v, 2)


class SubmissionReject(BaseModel):
    """Schema for rejecting a submission."""
    reject_reason: str = Field(..., min_length=1, description="驳回原因")


class SubmissionResponse(BaseModel):
    """Submission response schema."""
    id: int = Field(..., description="提交ID")
    task_id: int = Field(..., description="任务ID")
    task_title: Optional[str] = Field(default=None, description="任务标题")
    student_id: int = Field(..., description="学生ID")
    lesson_plan_path: Optional[str] = Field(default=None, description="教案文件路径")
    lesson_plan_name: Optional[str] = Field(default=None, description="教案文件名")
    video_path: Optional[str] = Field(default=None, description="视频文件路径")
    video_name: Optional[str] = Field(default=None, description="视频文件名")
    student_remark: Optional[str] = Field(default=None, description="学生备注")
    status: SubmissionStatus = Field(..., description="提交状态")
    lesson_plan_score: Optional[float] = Field(default=None, description="教案分数")
    video_score: Optional[float] = Field(default=None, description="视频分数")
    total_score: Optional[float] = Field(default=None, description="总分")
    feedback: Optional[str] = Field(default=None, description="老师评语")
    reject_reason: Optional[str] = Field(default=None, description="驳回原因")
    submitted_at: Optional[datetime] = Field(default=None, description="提交时间")
    reviewed_at: Optional[datetime] = Field(default=None, description="评阅时间")
    submit_count: int = Field(..., description="提交次数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 关联信息
    student: Optional[UserResponse] = Field(default=None, description="学生信息")
    task: Optional[TaskResponse] = Field(default=None, description="任务信息")
    
    model_config = {"from_attributes": True}


class SubmissionStatusOverview(BaseModel):
    """Overview of submission status for a student."""
    total_tasks: int = Field(..., description="总任务数")
    submitted: int = Field(..., description="已提交数")
    pending: int = Field(..., description="待审核数")
    approved: int = Field(..., description="已通过数")
    rejected: int = Field(..., description="已驳回数")
    not_submitted: int = Field(..., description="未提交数")
