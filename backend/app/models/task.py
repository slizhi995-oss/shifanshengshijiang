"""
Task model for instructor-published requirements.
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.semester import Semester
    from app.models.submission import Submission


class Task(Base):
    """
    Task table - stores requirements published by instructors.
    Supports rich text content for detailed instructions.
    """
    __tablename__ = "tasks"
    
    # 任务标题
    title: Mapped[str] = mapped_column(
        String(256), 
        nullable=False,
        comment="任务标题"
    )
    
    # 任务内容 (富文本)
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="任务内容(富文本)"
    )
    
    # 批次ID
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False,
        comment="批次ID"
    )
    
    # 发布老师ID
    instructor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="发布老师ID"
    )
    
    # 截止日期
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True,
        comment="截止日期"
    )
    
    # 是否要求上传教案
    require_lesson_plan: Mapped[bool] = mapped_column(
        Boolean, 
        default=True,
        comment="是否要求上传教案"
    )
    
    # 是否要求上传视频
    require_video: Mapped[bool] = mapped_column(
        Boolean, 
        default=True,
        comment="是否要求上传视频"
    )
    
    # 是否已发布
    is_published: Mapped[bool] = mapped_column(
        Boolean, 
        default=False,
        comment="是否已发布"
    )
    
    # 附件路径 (可选的参考资料)
    attachment_path: Mapped[Optional[str]] = mapped_column(
        String(512), 
        nullable=True,
        comment="附件路径"
    )
    
    # ==================== Relationships ====================
    
    semester: Mapped["Semester"] = relationship(
        "Semester",
        back_populates="tasks"
    )
    
    instructor: Mapped["User"] = relationship(
        "User",
        back_populates="tasks"
    )
    
    submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        back_populates="task",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title}, instructor={self.instructor_id})>"
