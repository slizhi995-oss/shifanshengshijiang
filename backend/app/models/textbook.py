"""Versioned textbooks, reviewed chapters and chapter-bound image assets."""
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Textbook(Base):
    __tablename__ = "textbooks"
    title: Mapped[str] = mapped_column(String(160))
    subject: Mapped[str] = mapped_column(String(40))
    grade: Mapped[str] = mapped_column(String(30))
    edition: Mapped[str] = mapped_column(String(160), default="")
    volume: Mapped[str] = mapped_column(String(80), default="")
    publisher: Mapped[str] = mapped_column(String(100), default="")
    file_path: Mapped[str] = mapped_column(String(512))
    original_filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="ready")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)


class TextbookPage(Base):
    __tablename__ = "textbook_pages"
    __table_args__ = (UniqueConstraint("book_id", "page_number"),)
    book_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)


class TextbookChapter(Base):
    __tablename__ = "textbook_chapters"
    book_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    parent_title: Mapped[str] = mapped_column(String(160), default="")
    start_page: Mapped[int] = mapped_column(Integer)
    end_page: Mapped[int] = mapped_column(Integer)
    printed_pages: Mapped[str] = mapped_column(String(80), default="")
    content: Mapped[str] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)


class TextbookAsset(Base):
    __tablename__ = "textbook_assets"
    asset_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id"), index=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("textbook_chapters.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    file_path: Mapped[str] = mapped_column(String(512))
    pdf_page: Mapped[int] = mapped_column(Integer)
    figure_number: Mapped[str] = mapped_column(String(60), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    conditions: Mapped[str] = mapped_column(Text, default="")
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)


class TextbookLesson(Base):
    __tablename__ = "textbook_lessons"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("textbook_chapters.id"))
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[str] = mapped_column(Text)
