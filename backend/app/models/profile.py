"""
学生成长画像模型
用于存储学生的能力画像快照和趋势数据
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Text, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.semester import Semester


class ProfileSnapshot(Base):
    """
    画像快照表 - 存储学生每次计算的能力画像
    用于支持成长趋势分析和能力雷达图展示
    """
    __tablename__ = "profile_snapshots"
    
    # 学生ID
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="学生ID"
    )
    
    # 批次ID (可选，用于按批次统计)
    semester_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"),
        nullable=True,
        comment="批次ID"
    )
    
    # 来源提交ID (可选，记录触发计算的提交)
    computed_from_submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="来源提交ID"
    )
    
    # ==================== 画像数据 ====================
    
    # 雷达图维度分数 (JSON)
    # 格式: {
    #   "lesson_plan": {"structure": 85, "objectives": 90, ...},
    #   "video": {"speech": 80, "gesture": 75, ...},
    #   "interaction": {"response_quality": 85, ...}
    # }
    radar_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="雷达图维度分数(JSON)"
    )
    
    # 趋势数据缓存 (JSON)
    # 格式: [{"date": "2024-01-01", "total_score": 85, "lesson_plan_score": 80, ...}, ...]
    trend_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="趋势数据缓存(JSON)"
    )
    
    # 行动建议 (JSON)
    # 格式: [{"dimension": "语速控制", "priority": 1, "suggestion": "..."}, ...]
    action_items_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="行动建议(JSON)"
    )
    
    # 综合能力评分 (0-100)
    overall_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="综合能力评分"
    )
    
    # 提交统计
    total_submissions: Mapped[int] = mapped_column(
        default=0,
        comment="总提交次数"
    )
    
    approved_submissions: Mapped[int] = mapped_column(
        default=0,
        comment="已通过次数"
    )
    
    # ==================== Relationships ====================
    
    student: Mapped["User"] = relationship(
        "User",
        foreign_keys=[student_id],
        backref="profile_snapshots"
    )
    
    semester: Mapped[Optional["Semester"]] = relationship(
        "Semester",
        foreign_keys=[semester_id]
    )
    
    def __repr__(self) -> str:
        return f"<ProfileSnapshot(id={self.id}, student={self.student_id}, semester={self.semester_id})>"


class PracticeSession(Base):
    """
    备课助手练习会话表
    用于存储学生的练习会话，便于画像统计
    """
    __tablename__ = "practice_sessions"
    
    # 学生ID
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="学生ID"
    )
    
    # 关联提交ID (可选)
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联提交ID"
    )
    
    # 会话标题
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="会话标题"
    )
    
    # 年级
    grade: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="年级"
    )
    
    # AI性格类型
    personality: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="AI性格类型"
    )
    
    # 对话历史 (JSON)
    messages_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="对话历史(JSON)"
    )
    
    # 练习报告 (JSON)
    report_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="练习报告(JSON)"
    )
    
    # 对话轮数
    message_count: Mapped[int] = mapped_column(
        default=0,
        comment="对话轮数"
    )
    
    # 整体评分 (从报告中提取)
    overall_rating: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="整体评分"
    )
    
    # 开始时间
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        comment="开始时间"
    )
    
    # 结束时间
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="结束时间"
    )
    
    # ==================== Relationships ====================
    
    student: Mapped["User"] = relationship(
        "User",
        foreign_keys=[student_id],
        backref="practice_sessions"
    )
    
    def __repr__(self) -> str:
        return f"<PracticeSession(id={self.id}, student={self.student_id}, title={self.title})>"
