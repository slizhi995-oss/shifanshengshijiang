"""English audio catalog, persisted text vectors, and owner-scoped lesson matches."""
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AudioResource(Base):
    __tablename__ = 'audio_resources'
    resource_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    relative_path: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    textbook_sha256: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(String(40), default='英语')
    stage: Mapped[str] = mapped_column(String(20))
    series: Mapped[str] = mapped_column(String(80))
    volume: Mapped[str] = mapped_column(String(80))
    unit_type: Mapped[str] = mapped_column(String(30))
    unit_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_title: Mapped[str] = mapped_column(String(180))
    section: Mapped[str] = mapped_column(String(160), default='')
    audio_kind: Mapped[str] = mapped_column(String(80), default='')
    printed_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text)
    vector_json: Mapped[str] = mapped_column(Text, default='{}')


class AudioVectorIndex(Base):
    __tablename__ = 'audio_vector_indexes'
    version: Mapped[str] = mapped_column(String(64))
    algorithm: Mapped[str] = mapped_column(String(60), default='tfidf-cosine-v1')
    idf_json: Mapped[str] = mapped_column(Text)


class AudioLesson(Base):
    __tablename__ = 'audio_lessons'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    textbook_lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey('textbook_lessons.id'), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(180))
    subject: Mapped[str] = mapped_column(String(40))
    grade: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    source_json: Mapped[str] = mapped_column(Text, default='{}')
    matches_json: Mapped[str] = mapped_column(Text, default='[]')
    matched_version: Mapped[str] = mapped_column(String(64), default='')
    match_status: Mapped[str] = mapped_column(String(40), default='pending')
