"""
AI 模型配置模型
用于存储多个 AI 模型的 API 配置，支持管理员动态管理
"""
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Boolean, Text, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AIModelConfig(Base):
    """
    AI 模型配置表 - 存储可用的 AI 模型 API 配置
    """
    __tablename__ = "ai_model_configs"
    
    # 模型名称（显示名称）
    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="模型显示名称"
    )
    
    # 模型提供商: dashscope, openai, azure, anthropic 等
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="模型提供商"
    )
    
    # 模型标识符（API 中使用的模型名称）
    model_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="模型API标识符"
    )
    
    # API Key（加密存储）
    api_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="API密钥"
    )
    
    # API 基础 URL（可选，用于自定义端点）
    api_base_url: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="API基础URL"
    )
    
    # 模型类型: text, audio, vision
    model_type: Mapped[str] = mapped_column(
        String(32),
        default="text",
        comment="模型类型: text/audio/vision"
    )
    
    # 是否启用
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否启用"
    )
    
    # 是否为默认模型
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否为默认模型"
    )
    
    # 排序优先级（越小越靠前）
    priority: Mapped[int] = mapped_column(
        Integer,
        default=100,
        comment="排序优先级"
    )
    
    # 单次调用 Token 限制
    max_tokens: Mapped[int] = mapped_column(
        Integer,
        default=4096,
        comment="单次调用最大Token数"
    )
    
    # 温度参数
    temperature: Mapped[float] = mapped_column(
        Float,
        default=0.7,
        comment="温度参数"
    )
    
    # 单价（每千 Token，单位：元）
    price_per_1k_tokens: Mapped[float] = mapped_column(
        Float,
        default=0.002,
        comment="每千Token价格(元)"
    )
    
    # 描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="模型描述"
    )
    
    # 备注
    remark: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="备注信息"
    )

    # 月度额度（Token 数，None 表示不限额）
    monthly_quota: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        comment="月度Token额度，None表示不限"
    )

    def __repr__(self) -> str:
        return f"<AIModelConfig(id={self.id}, name={self.name}, provider={self.provider}, model={self.model_id})>"


class AIModelUsageLog(Base):
    """
    AI 模型使用日志 - 记录每次 AI 调用的详细信息
    用于统计和分析
    """
    __tablename__ = "ai_model_usage_logs"
    
    # 使用的模型配置 ID
    model_config_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="模型配置ID"
    )
    
    # 用户 ID
    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="用户ID"
    )
    
    # 关联的提交 ID（可选）
    submission_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="关联提交ID"
    )
    
    # 调用类型: lesson_plan_analysis, video_analysis, chat, etc.
    usage_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="调用类型"
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
    
    # 音频秒数（如果适用）
    audio_seconds: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="音频秒数"
    )
    
    # 调用耗时（毫秒）
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="调用耗时(ms)"
    )
    
    # 估算成本（元）
    estimated_cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="估算成本(元)"
    )
    
    # 是否成功
    is_success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否成功"
    )
    
    # 错误信息（如果失败）
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )
    
    def __repr__(self) -> str:
        return f"<AIModelUsageLog(id={self.id}, user={self.user_id}, type={self.usage_type}, tokens={self.input_tokens + self.output_tokens})>"
