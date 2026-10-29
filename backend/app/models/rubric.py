"""
评分规则(Rubric)模型
支持老师自定义评分维度和权重
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, String, Text, Float, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.semester import Semester


class GradingRubric(Base):
    """
    评分规则表
    支持老师为每个批次定义评分规则
    """
    __tablename__ = "grading_rubrics"
    
    # 规则名称
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="规则名称"
    )
    
    # 规则描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="规则描述"
    )
    
    # 创建者（老师）ID
    instructor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者ID"
    )
    
    # 批次ID（可选，为空则为通用规则）
    semester_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"),
        nullable=True,
        comment="批次ID"
    )
    
    # 是否为默认规则
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否为默认规则"
    )
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否启用"
    )
    
    # ==================== 权重配置 ====================
    
    # 教案权重 (0-100)
    lesson_plan_weight: Mapped[float] = mapped_column(
        Float,
        default=40.0,
        comment="教案权重(0-100)"
    )
    
    # 视频权重 (0-100)
    video_weight: Mapped[float] = mapped_column(
        Float,
        default=60.0,
        comment="视频权重(0-100)"
    )
    
    # ==================== 教案评分维度配置 (JSON) ====================
    
    # 教案维度配置
    # 格式: [{"name": "结构", "key": "structure", "weight": 15, "description": "..."}]
    lesson_plan_dimensions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="教案评分维度配置(JSON)"
    )
    
    # ==================== 视频评分维度配置 (JSON) ====================
    
    # 视频维度配置
    video_dimensions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="视频评分维度配置(JSON)"
    )
    
    # ==================== 评分等级配置 (JSON) ====================
    
    # 评分等级
    # 格式: [{"min": 90, "max": 100, "label": "优秀", "description": "..."}]
    grade_levels: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="评分等级配置(JSON)"
    )
    
    # ==================== Relationships ====================
    
    instructor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[instructor_id]
    )
    
    semester: Mapped[Optional["Semester"]] = relationship(
        "Semester",
        foreign_keys=[semester_id]
    )
    
    def __repr__(self) -> str:
        return f"<GradingRubric(id={self.id}, name={self.name})>"


class AICallLog(Base):
    """
    AI 调用日志表
    记录所有 AI 接口调用，用于审计和统计
    """
    __tablename__ = "ai_call_logs"
    
    # 调用者ID
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="调用者ID"
    )
    
    # 关联的提交ID（可选）
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联提交ID"
    )
    
    # 调用类型
    call_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="调用类型: analyze/summary/improve/generate/video_analyze/chat"
    )
    
    # AI 服务商
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="AI服务商"
    )
    
    # 模型名称
    model: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="模型名称"
    )
    
    # 输入 Token 数
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="输入Token数"
    )
    
    # 输出 Token 数
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="输出Token数"
    )
    
    # 音频秒数（视频分析时）
    audio_seconds: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="音频秒数"
    )
    
    # 耗时（毫秒）
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="耗时(毫秒)"
    )
    
    # 是否成功
    is_success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否成功"
    )
    
    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )
    
    # 请求概要（不存储完整内容，防止隐私泄露）
    request_summary: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="请求概要"
    )
    
    # IP 地址
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="IP地址"
    )
    
    # ==================== Relationships ====================
    
    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[user_id]
    )
    
    def __repr__(self) -> str:
        return f"<AICallLog(id={self.id}, type={self.call_type}, success={self.is_success})>"
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    @property
    def estimated_cost(self) -> float:
        """估算成本(RMB)"""
        # 按通义千问价格估算
        token_cost = self.total_tokens / 1000 * 0.002
        audio_cost = self.audio_seconds / 60 * 0.01
        return round(token_cost + audio_cost, 4)
