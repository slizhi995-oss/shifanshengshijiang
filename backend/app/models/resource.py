"""
Resource model for the student Resource Center.
Stores teaching videos, observation lessons, external links, and excellent topics.
"""
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import String, Text, Boolean, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ResourceCategory(PyEnum):
    """资源分类"""
    VIDEO = "video"             # 教学视频
    OBSERVATION = "observation"  # 观摩课程
    WEBSITE = "website"         # 资源网站
    TOPIC = "topic"             # 优秀选题
    DOCUMENT = "document"       # 教学文档


class Resource(Base):
    """
    Resource table - stores educational resources for student resource center.
    """
    __tablename__ = "resources"

    # 资源标题
    title: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="资源标题"
    )

    # 资源描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="资源描述"
    )

    # 资源分类
    category: Mapped[ResourceCategory] = mapped_column(
        Enum(ResourceCategory),
        nullable=False,
        comment="资源分类: video/observation/website/topic/document"
    )

    # 资源链接（视频URL / 外部网站URL）
    url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        comment="资源链接"
    )

    # 封面图片
    cover_image: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="封面图片URL"
    )

    # 标签（JSON数组字符串，如 '["语文","小学","课堂导入"]'）
    tags: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        comment="标签JSON数组"
    )

    # 学科
    subject: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="学科"
    )

    # 学段
    grade_level: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="适用学段"
    )

    # 来源/作者
    source: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="来源/作者"
    )

    # 浏览次数
    view_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        comment="浏览次数"
    )

    # 推荐权重（用于排序）
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        comment="排序权重，越大越靠前"
    )

    # 是否发布
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        comment="是否发布"
    )

    # 是否推荐（首页精选）
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        comment="是否精选推荐"
    )

    # 富文本内容（用于优秀选题等需要详细内容的资源）
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="详细内容(富文本)"
    )

    def __repr__(self) -> str:
        return f"<Resource(id={self.id}, title={self.title}, category={self.category})>"
