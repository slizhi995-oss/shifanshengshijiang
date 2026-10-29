"""
通知模型
存储用户通知（任务发布、作业批改、AI分析完成等）
"""
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    """用户通知表"""
    __tablename__ = "notifications"

    # 接收者
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="接收者ID"
    )

    # 通知类型: system/task/grade/ai/message/comment
    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="system",
        comment="通知类型"
    )

    # 标题
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="通知标题"
    )

    # 内容
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="通知内容"
    )

    # 是否已读
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否已读"
    )

    # 跳转链接（可选）
    link: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="跳转链接"
    )

    # 关联的提交ID（可选）
    submission_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="关联提交ID"
    )

    # ==================== Relationships ====================
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.type}, user_id={self.user_id})>"
