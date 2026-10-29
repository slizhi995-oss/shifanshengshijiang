"""
Semester model for managing lecture practice periods.
"""
from enum import Enum as PyEnum
from datetime import date
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Date, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.task import Task
    from app.models.notice import Notice


class SemesterStatus(str, PyEnum):
    """Semester status enumeration."""
    DRAFT = "draft"          # 草稿/未开始
    ACTIVE = "active"        # 进行中
    COMPLETED = "completed"  # 已结束


class Semester(Base):
    """
    Semester table - represents a lecture practice period/batch.
    Example: "2025春季试讲", "2024秋季试讲"
    """
    __tablename__ = "semesters"
    
    # 批次名称
    name: Mapped[str] = mapped_column(
        String(128), 
        unique=True, 
        nullable=False,
        comment="批次名称"
    )
    
    # 批次状态
    status: Mapped[SemesterStatus] = mapped_column(
        Enum(SemesterStatus), 
        default=SemesterStatus.DRAFT,
        comment="批次状态"
    )
    
    # 开始日期
    start_date: Mapped[Optional[date]] = mapped_column(
        Date, 
        nullable=True,
        comment="开始日期"
    )
    
    # 结束日期
    end_date: Mapped[Optional[date]] = mapped_column(
        Date, 
        nullable=True,
        comment="结束日期"
    )
    
    # 描述
    description: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="批次描述"
    )
    
    # ==================== Relationships ====================
    
    # 该批次下的分组
    groups: Mapped[List["Group"]] = relationship(
        "Group",
        back_populates="semester",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    # 该批次下的任务
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="semester",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    # 该批次下的通知
    notices: Mapped[List["Notice"]] = relationship(
        "Notice",
        back_populates="semester",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<Semester(id={self.id}, name={self.name}, status={self.status})>"
