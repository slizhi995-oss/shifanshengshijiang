"""
Submission model for student assignment submissions.
"""
from enum import Enum as PyEnum
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, String, Text, Enum, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.task import Task


class SubmissionStatus(str, PyEnum):
    """Submission status enumeration."""
    PENDING = "pending"      # 待批改
    GRADED = "graded"        # 已评分（待确认通过/驳回）
    APPROVED = "approved"    # 已通过
    REJECTED = "rejected"    # 已驳回


class Submission(Base):
    """
    Submission table - stores student submissions.
    Includes file paths, scores, and feedback.
    """
    __tablename__ = "submissions"
    
    # 任务ID
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="任务ID"
    )
    
    # 学生ID
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="学生ID"
    )
    
    # 教案文件路径 (PDF)
    lesson_plan_path: Mapped[Optional[str]] = mapped_column(
        String(512), 
        nullable=True,
        comment="教案文件路径"
    )
    
    # 教案文件名
    lesson_plan_name: Mapped[Optional[str]] = mapped_column(
        String(256), 
        nullable=True,
        comment="教案文件名"
    )
    
    # 视频文件路径
    video_path: Mapped[Optional[str]] = mapped_column(
        String(512), 
        nullable=True,
        comment="视频文件路径"
    )
    
    # 视频文件名
    video_name: Mapped[Optional[str]] = mapped_column(
        String(256), 
        nullable=True,
        comment="视频文件名"
    )
    
    # 学生备注
    student_remark: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="学生备注"
    )
    
    # 提交状态
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, values_callable=lambda x: [e.value for e in x]), 
        default=SubmissionStatus.PENDING,
        comment="提交状态"
    )
    
    # ==================== 评分相关 ====================
    
    # 教案分数 (0-100)
    lesson_plan_score: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="教案分数"
    )
    
    # 视频分数 (0-100)
    video_score: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="视频分数"
    )
    
    # 总分 (0-100)
    total_score: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="总分"
    )
    
    # 老师评语
    feedback: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="老师评语"
    )
    
    # 驳回原因
    reject_reason: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="驳回原因"
    )
    
    # 提交时间
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True,
        comment="提交时间"
    )
    
    # 评阅时间
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True,
        comment="评阅时间"
    )
    
    # 提交次数 (用于追踪重新提交)
    submit_count: Mapped[int] = mapped_column(
        default=0,
        comment="提交次数"
    )
    
    # ==================== AI 分析结果 ====================
    
    # 教案 AI 分析结果 (JSON)
    lesson_plan_analysis: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="教案AI分析结果(JSON)"
    )
    
    # 视频 AI 分析结果 (JSON)
    video_analysis: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="视频AI分析结果(JSON)"
    )
    
    # AI 建议评语
    ai_suggested_feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI建议评语"
    )
    
    # AI 建议分数
    ai_suggested_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="AI建议分数"
    )
    
    # ==================== Relationships ====================
    
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="submissions"
    )
    
    student: Mapped["User"] = relationship(
        "User",
        back_populates="submissions"
    )
    
    def __repr__(self) -> str:
        return f"<Submission(id={self.id}, task={self.task_id}, student={self.student_id}, status={self.status})>"
