"""Private video searches and confirmed video references for generated lessons."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LessonVideoSearch(Base):
    __tablename__ = 'lesson_video_searches'
    lesson_id: Mapped[int] = mapped_column(ForeignKey('audio_lessons.id'), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default='idle')
    run_id: Mapped[str] = mapped_column(String(32), default='')
    fingerprint: Mapped[str] = mapped_column(String(64), default='')
    query: Mapped[str] = mapped_column(String(160), default='')
    needs_json: Mapped[str] = mapped_column(Text, default='[]')
    items_json: Mapped[str] = mapped_column(Text, default='[]')
    message: Mapped[str] = mapped_column(String(400), default='')
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LessonVideo(Base):
    __tablename__ = 'lesson_videos'
    __table_args__ = (UniqueConstraint('lesson_id', 'bvid', 'page', name='uq_lesson_video_page'),)
    lesson_id: Mapped[int] = mapped_column(ForeignKey('audio_lessons.id'), index=True)
    bvid: Mapped[str] = mapped_column(String(12))
    page: Mapped[int] = mapped_column(default=1)
    title: Mapped[str] = mapped_column(String(256))
    section: Mapped[str] = mapped_column(String(100), default='')
    purpose: Mapped[str] = mapped_column(String(400), default='')
    source: Mapped[str] = mapped_column(String(32), default='manual')


class LessonWebResource(Base):
    """General public references; legacy Bilibili selections remain in lesson_videos."""
    __tablename__ = 'lesson_web_resources'
    __table_args__ = (UniqueConstraint('lesson_id', 'url_key', name='uq_lesson_web_resource_url'),)
    lesson_id: Mapped[int] = mapped_column(ForeignKey('audio_lessons.id'), index=True)
    url_key: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(256))
    site_name: Mapped[str] = mapped_column(String(128), default='')
    resource_type: Mapped[str] = mapped_column(String(32), default='webpage')
    cover_url: Mapped[str] = mapped_column(Text, default='')
    section: Mapped[str] = mapped_column(String(100), default='')
    purpose: Mapped[str] = mapped_column(String(400), default='')
    source: Mapped[str] = mapped_column(String(32), default='manual')
