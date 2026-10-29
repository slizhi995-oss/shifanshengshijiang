"""
Message model for student-instructor communication.
"""
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.semester import Semester


class Message(Base):
    """
    Message table - simple message board for student-instructor communication.
    """
    __tablename__ = "messages"
    
    # 发送者ID
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="发送者ID"
    )
    
    # 接收者ID
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="接收者ID"
    )
    
    # 批次ID（用于按批次分组）
    semester_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"),
        nullable=True,
        comment="批次ID"
    )
    
    # 消息内容
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="消息内容"
    )
    
    # 是否已读
    is_read: Mapped[bool] = mapped_column(
        Boolean, 
        default=False,
        comment="是否已读"
    )
    
    # ==================== Relationships ====================
    
    sender: Mapped["User"] = relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="sent_messages"
    )
    
    receiver: Mapped["User"] = relationship(
        "User",
        foreign_keys=[receiver_id],
        back_populates="received_messages"
    )
    
    semester: Mapped[Optional["Semester"]] = relationship(
        "Semester",
        foreign_keys=[semester_id]
    )
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, from={self.sender_id}, to={self.receiver_id})>"
