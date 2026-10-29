"""
Notice model for system-wide announcements.
"""
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, String, Text, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.semester import Semester
    from app.models.user import User


class DisplayType(PyEnum):
    """公告显示类型"""
    DIALOG = "dialog"       # 弹窗
    MARQUEE = "marquee"     # 跑马灯
    BOTH = "both"           # 两者都有


class Notice(Base):
    """
    Notice table - stores system announcements.
    Published by admin for all users.
    """
    __tablename__ = "notices"
    
    # 通知标题
    title: Mapped[str] = mapped_column(
        String(256), 
        nullable=False,
        comment="通知标题"
    )
    
    # 通知内容 (富文本)
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="通知内容"
    )
    
    # 关联批次 (可选，用于针对特定批次的通知)
    semester_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联批次ID"
    )
    
    # 是否置顶
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, 
        default=False,
        comment="是否置顶"
    )
    
    # 是否已发布
    is_published: Mapped[bool] = mapped_column(
        Boolean, 
        default=True,
        comment="是否已发布"
    )
    
    # 是否在登录页展示
    show_on_login: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否在登录页展示"
    )
    
    # 显示类型
    display_type: Mapped[Optional[DisplayType]] = mapped_column(
        Enum(DisplayType),
        nullable=True,
        default=DisplayType.DIALOG,
        server_default="dialog",
        comment="显示类型: dialog-弹窗, marquee-跑马灯, both-两者"
    )
    
    # 附件路径
    attachment_path: Mapped[Optional[str]] = mapped_column(
        String(512), 
        nullable=True,
        comment="附件路径"
    )
    
    # ==================== Relationships ====================
    
    semester: Mapped[Optional["Semester"]] = relationship(
        "Semester",
        back_populates="notices"
    )
    
    def __repr__(self) -> str:
        return f"<Notice(id={self.id}, title={self.title}, is_published={self.is_published})>"


class NoticeRead(Base):
    """
    NoticeRead table - tracks which users have read which notices.
    """
    __tablename__ = "notice_reads"
    
    # 用户ID
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID"
    )
    
    # 公告ID
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE"),
        nullable=False,
        comment="公告ID"
    )
    
    # ==================== Relationships ====================
    
    user: Mapped["User"] = relationship("User")
    notice: Mapped["Notice"] = relationship("Notice")
    
    def __repr__(self) -> str:
        return f"<NoticeRead(user_id={self.user_id}, notice_id={self.notice_id})>"
