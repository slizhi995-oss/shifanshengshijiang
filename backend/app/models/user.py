"""
User model for all system users (Admin, Instructor, Student).
"""
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Boolean, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.task import Task
    from app.models.submission import Submission
    from app.models.message import Message


class UserRole(str, PyEnum):
    """User role enumeration."""
    ADMIN = "admin"
    INSTRUCTOR = "instructor"
    STUDENT = "student"


class User(Base):
    """
    User table - stores all system users.
    Users are imported by admin, not self-registered.
    """
    __tablename__ = "users"
    
    # 工号/学号 - unique identifier for login
    user_code: Mapped[str] = mapped_column(
        String(32), 
        unique=True, 
        index=True, 
        nullable=False,
        comment="工号/学号"
    )
    
    # 姓名
    name: Mapped[str] = mapped_column(
        String(64), 
        nullable=False,
        comment="姓名"
    )
    
    # 密码 (hashed)
    password_hash: Mapped[str] = mapped_column(
        String(256), 
        nullable=False,
        comment="密码哈希"
    )
    
    # 角色
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), 
        nullable=False,
        comment="用户角色"
    )
    
    # 是否为默认密码 - 用于强制修改密码逻辑
    is_default_password: Mapped[bool] = mapped_column(
        Boolean, 
        default=True,
        comment="是否为默认密码"
    )
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True,
        comment="是否启用"
    )
    
    # 是否为超级管理员
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否为超级管理员"
    )
    
    # 联系方式 (可选)
    email: Mapped[Optional[str]] = mapped_column(
        String(128), 
        nullable=True,
        comment="邮箱"
    )
    
    phone: Mapped[Optional[str]] = mapped_column(
        String(20), 
        nullable=True,
        comment="手机号"
    )
    
    # 头像 (可选)
    avatar: Mapped[Optional[str]] = mapped_column(
        String(256), 
        nullable=True,
        comment="头像URL"
    )
    
    # 备注
    remark: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="备注"
    )
    
    # 学院
    college: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="学院"
    )

    # 专业
    major: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="专业"
    )

    # 班级
    class_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="班级"
    )

    # 班主任
    head_teacher: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="班主任"
    )
    
    # ==================== Relationships ====================
    
    # 作为指导老师时管理的分组
    instructor_groups: Mapped[List["Group"]] = relationship(
        "Group",
        foreign_keys="Group.instructor_id",
        back_populates="instructor",
        lazy="selectin"
    )
    
    # 作为学生时所属的分组
    student_groups: Mapped[List["Group"]] = relationship(
        "Group",
        foreign_keys="Group.student_id",
        back_populates="student",
        lazy="selectin"
    )
    
    # 发布的任务 (指导老师)
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="instructor",
        lazy="selectin"
    )
    
    # 提交的作业 (学生)
    submissions: Mapped[List["Submission"]] = relationship(
        "Submission",
        back_populates="student",
        lazy="selectin"
    )
    
    # 发送的消息
    sent_messages: Mapped[List["Message"]] = relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        lazy="selectin"
    )
    
    # 接收的消息
    received_messages: Mapped[List["Message"]] = relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, code={self.user_code}, name={self.name}, role={self.role})>"
