"""Administrator-curated Bilibili tips shown when lesson resources are absent."""
from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TeachingTipVideo(Base):
    __tablename__ = 'teaching_tip_videos'
    __table_args__ = (UniqueConstraint('bvid', 'page', name='uq_teaching_tip_video_page'),)

    bvid: Mapped[str] = mapped_column(String(12))
    page: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(64), default='试讲技巧')
    description: Mapped[str] = mapped_column(Text, default='')
    cover_url: Mapped[str] = mapped_column(Text, default='')
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
