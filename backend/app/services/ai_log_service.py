"""
AI 调用日志服务
记录所有 AI 接口调用，用于审计、统计和成本追踪
"""
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.models.rubric import AICallLog
from app.core.config import settings


class AILogService:
    """AI 调用日志服务"""
    
    async def log_call(
        self,
        db: AsyncSession,
        call_type: str,
        user_id: Optional[int] = None,
        submission_id: Optional[int] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        audio_seconds: float = 0.0,
        latency_ms: int = 0,
        is_success: bool = True,
        error_message: Optional[str] = None,
        request_summary: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AICallLog:
        """
        记录 AI 调用日志
        
        Args:
            db: 数据库会话
            call_type: 调用类型
            user_id: 调用者ID
            submission_id: 关联提交ID
            input_tokens: 输入token数
            output_tokens: 输出token数
            audio_seconds: 音频秒数
            latency_ms: 耗时(毫秒)
            is_success: 是否成功
            error_message: 错误信息
            request_summary: 请求概要
            ip_address: IP地址
        """
        log = AICallLog(
            call_type=call_type,
            user_id=user_id,
            submission_id=submission_id,
            provider=settings.AI_PROVIDER,
            model=self._get_current_model(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            audio_seconds=audio_seconds,
            latency_ms=latency_ms,
            is_success=is_success,
            error_message=error_message,
            request_summary=request_summary[:256] if request_summary else None,
            ip_address=ip_address
        )
        
        db.add(log)
        await db.commit()
        await db.refresh(log)
        
        return log
    
    def _get_current_model(self) -> str:
        """获取当前使用的模型名称"""
        provider = settings.AI_PROVIDER.lower()
        if provider == "dashscope":
            return settings.DASHSCOPE_MODEL
        elif provider == "openai":
            return settings.OPENAI_MODEL
        elif provider == "deepseek":
            return settings.DEEPSEEK_MODEL
        return "unknown"
    
    async def get_statistics(
        self,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取 AI 调用统计
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        stmt = select(AICallLog).where(
            and_(
                AICallLog.created_at >= start_date,
                AICallLog.created_at <= end_date
            )
        )
        
        if user_id:
            stmt = stmt.where(AICallLog.user_id == user_id)
        
        result = await db.execute(stmt)
        logs = list(result.scalars().all())
        
        total_calls = len(logs)
        success_calls = sum(1 for l in logs if l.is_success)
        failed_calls = total_calls - success_calls
        
        total_input_tokens = sum(l.input_tokens for l in logs)
        total_output_tokens = sum(l.output_tokens for l in logs)
        total_audio_seconds = sum(l.audio_seconds for l in logs)
        total_latency = sum(l.latency_ms for l in logs)
        
        # 按类型统计
        by_type = {}
        for log in logs:
            if log.call_type not in by_type:
                by_type[log.call_type] = {"count": 0, "tokens": 0, "success": 0}
            by_type[log.call_type]["count"] += 1
            by_type[log.call_type]["tokens"] += log.input_tokens + log.output_tokens
            if log.is_success:
                by_type[log.call_type]["success"] += 1
        
        # 估算成本
        token_cost = (total_input_tokens + total_output_tokens) / 1000 * 0.002
        audio_cost = total_audio_seconds / 60 * 0.01
        total_cost = token_cost + audio_cost
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "calls": {
                "total": total_calls,
                "success": success_calls,
                "failed": failed_calls,
                "success_rate": round(success_calls / total_calls * 100, 2) if total_calls > 0 else 0
            },
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens
            },
            "audio_seconds": round(total_audio_seconds, 1),
            "latency": {
                "total_ms": total_latency,
                "avg_ms": round(total_latency / total_calls) if total_calls > 0 else 0
            },
            "cost": {
                "token_cost_rmb": round(token_cost, 4),
                "audio_cost_rmb": round(audio_cost, 4),
                "total_rmb": round(total_cost, 4)
            },
            "by_type": by_type
        }
    
    async def get_recent_errors(
        self,
        db: AsyncSession,
        limit: int = 20
    ) -> list:
        """
        获取最近的错误日志
        """
        stmt = select(AICallLog).where(
            AICallLog.is_success == False
        ).order_by(desc(AICallLog.created_at)).limit(limit)
        
        result = await db.execute(stmt)
        logs = list(result.scalars().all())
        
        return [
            {
                "id": l.id,
                "call_type": l.call_type,
                "user_id": l.user_id,
                "error_message": l.error_message,
                "request_summary": l.request_summary,
                "created_at": l.created_at.isoformat() if l.created_at else None
            }
            for l in logs
        ]
    
    async def get_daily_trend(
        self,
        db: AsyncSession,
        days: int = 7
    ) -> list:
        """
        获取每日调用趋势
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(AICallLog).where(
            AICallLog.created_at >= start_date
        ).order_by(AICallLog.created_at)
        
        result = await db.execute(stmt)
        logs = list(result.scalars().all())
        
        # 按日期分组
        daily_data = {}
        for log in logs:
            date_key = log.created_at.strftime("%Y-%m-%d") if log.created_at else "unknown"
            if date_key not in daily_data:
                daily_data[date_key] = {
                    "date": date_key,
                    "calls": 0,
                    "tokens": 0,
                    "errors": 0
                }
            daily_data[date_key]["calls"] += 1
            daily_data[date_key]["tokens"] += log.input_tokens + log.output_tokens
            if not log.is_success:
                daily_data[date_key]["errors"] += 1
        
        return sorted(daily_data.values(), key=lambda x: x["date"])


# 全局服务实例
ai_log_service = AILogService()


class AICallTimer:
    """
    AI 调用计时器（上下文管理器）
    用于自动记录调用时间和结果
    """
    
    def __init__(
        self,
        db: AsyncSession,
        call_type: str,
        user_id: Optional[int] = None,
        submission_id: Optional[int] = None,
        request_summary: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        self.db = db
        self.call_type = call_type
        self.user_id = user_id
        self.submission_id = submission_id
        self.request_summary = request_summary
        self.ip_address = ip_address
        
        self.start_time = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.audio_seconds = 0.0
        self.is_success = True
        self.error_message = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        latency_ms = int((time.time() - self.start_time) * 1000)
        
        if exc_type is not None:
            self.is_success = False
            self.error_message = str(exc_val)
        
        await ai_log_service.log_call(
            db=self.db,
            call_type=self.call_type,
            user_id=self.user_id,
            submission_id=self.submission_id,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            audio_seconds=self.audio_seconds,
            latency_ms=latency_ms,
            is_success=self.is_success,
            error_message=self.error_message,
            request_summary=self.request_summary,
            ip_address=self.ip_address
        )
        
        # 不抑制异常
        return False
    
    def set_tokens(self, input_tokens: int, output_tokens: int):
        """设置 token 数量"""
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
    
    def set_audio_seconds(self, seconds: float):
        """设置音频秒数"""
        self.audio_seconds = seconds
    
    def set_success(self, success: bool, error_message: Optional[str] = None):
        """设置成功状态"""
        self.is_success = success
        self.error_message = error_message
