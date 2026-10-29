from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TrialVideo(Base):
    __tablename__ = "trial_videos"

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    semester_id: Mapped[Optional[int]] = mapped_column(ForeignKey("semesters.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    subject: Mapped[str] = mapped_column(String(32), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    presenter_name: Mapped[str] = mapped_column(String(64), default="")
    presenter_type: Mapped[str] = mapped_column(String(16), default="student")
    original_name: Mapped[str] = mapped_column(String(255))
    file_name: Mapped[Optional[str]] = mapped_column(String(80))
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    blocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    moderation_reason: Mapped[str] = mapped_column(String(500), default="")
    file_status: Mapped[str] = mapped_column(String(16), default="available")
    analysis_status: Mapped[str] = mapped_column(String(16), default="pending")
    analysis_result: Mapped[Optional[dict]] = mapped_column(JSON)
    analysis_error: Mapped[str] = mapped_column(Text, default="")


class TrialVideoBlock(Base):
    __tablename__ = "trial_video_blocks"
    __table_args__ = (UniqueConstraint("owner_id", "sha256"),)

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(500), default="")


class TrialVideoComment(Base):
    __tablename__ = "trial_video_comments"
    __table_args__ = (Index("ix_trial_video_comments_video_created", "video_id", "created_at", "id"),)

    video_id: Mapped[int] = mapped_column(ForeignKey("trial_videos.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("trial_video_comments.id"), index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    content: Mapped[str] = mapped_column(String(1000))
