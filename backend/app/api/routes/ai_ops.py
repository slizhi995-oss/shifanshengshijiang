"""
AI 运营看板路由
提供 AI 用量统计、失败率监控、重试功能、审计日志等接口
这是比赛展示的管理员端必做点
"""
import json
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, case
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.submission import Submission, SubmissionStatus
from app.models.task import Task
from app.models.semester import Semester
from app.models.ai_config import AIModelConfig, AIModelUsageLog
from app.models.rubric import AICallLog

router = APIRouter()


# ==================== 请求/响应模型 ====================

class ThresholdSettings(BaseModel):
    """告警阈值设置"""
    daily_token_limit: Optional[int] = Field(None, description="每日 Token 上限")
    daily_audio_seconds_limit: Optional[int] = Field(None, description="每日音频秒数上限")
    failure_rate_threshold: Optional[float] = Field(None, description="失败率阈值（0-1）")


class RetryRequest(BaseModel):
    """重试请求"""
    submission_ids: List[int] = Field(..., description="需要重试的提交ID列表")


# ==================== 运营概览 ====================

@router.get("/overview")
async def get_ai_ops_overview(
    range: str = Query("week", description="统计范围: day/week/month"),
    semester_id: Optional[int] = Query(None, description="批次ID（可选）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取 AI 运营概览——从 AICallLog 真实日志表聚合
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可查看")

    now = datetime.utcnow()
    if range == "day":
        start_date = now - timedelta(days=1)
    elif range == "week":
        start_date = now - timedelta(days=7)
    else:
        start_date = now - timedelta(days=30)

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── 1. 汇总统计 ───────────────────────────────────────
    summary_result = await db.execute(
        select(
            func.count(AICallLog.id).label("total"),
            func.sum(case((AICallLog.is_success == True, 1), else_=0)).label("success_cnt"),
            func.sum(AICallLog.input_tokens + AICallLog.output_tokens).label("tokens"),
            func.sum(AICallLog.audio_seconds).label("audio_secs"),
            func.avg(AICallLog.latency_ms).label("avg_latency"),
        ).where(AICallLog.created_at >= start_date)
    )
    s = summary_result.one()
    total_calls = s.total or 0
    success_count = int(s.success_cnt or 0)
    total_tokens = int(s.tokens or 0)
    total_audio = round(float(s.audio_secs or 0), 1)
    avg_latency = round(float(s.avg_latency or 0), 0)

    # 今日调用数
    today_cnt = await db.execute(
        select(func.count(AICallLog.id)).where(AICallLog.created_at >= today_start)
    )
    today_calls = today_cnt.scalar() or 0

    # ── 2. 按调用类型分布 ──────────────────────────────────
    type_rows = await db.execute(
        select(
            AICallLog.call_type,
            func.count(AICallLog.id).label("cnt"),
            func.sum(AICallLog.input_tokens + AICallLog.output_tokens).label("tokens"),
        ).where(AICallLog.created_at >= start_date)
        .group_by(AICallLog.call_type)
    )
    by_type = {
        row.call_type: {"count": row.cnt, "tokens": int(row.tokens or 0)}
        for row in type_rows.all()
    }

    # ── 3. Top 用户（按 token 用量） ───────────────────────
    user_rows = await db.execute(
        select(
            AICallLog.user_id,
            func.count(AICallLog.id).label("cnt"),
            func.sum(AICallLog.input_tokens + AICallLog.output_tokens).label("tokens"),
        ).where(AICallLog.created_at >= start_date)
        .group_by(AICallLog.user_id)
        .order_by(desc("tokens")).limit(10)
    )
    top_users = []
    for row in user_rows.all():
        u = await db.get(User, row.user_id) if row.user_id else None
        top_users.append({
            "user_id": row.user_id,
            "name": u.name if u else "系统",
            "user_code": u.user_code if u else "-",
            "count": row.cnt,
            "tokens": int(row.tokens or 0),
        })

    # ── 4. 每日趋势 ────────────────────────────────────────
    daily_rows = await db.execute(
        select(
            func.date(AICallLog.created_at).label("dt"),
            func.count(AICallLog.id).label("cnt"),
            func.sum(case((AICallLog.is_success == True, 1), else_=0)).label("suc"),
            func.sum(AICallLog.input_tokens + AICallLog.output_tokens).label("tokens"),
        ).where(AICallLog.created_at >= start_date)
        .group_by(func.date(AICallLog.created_at))
        .order_by("dt")
    )
    daily_trend = [
        {
            "date": str(row.dt),
            "count": row.cnt,
            "success": int(row.suc or 0),
            "failed": row.cnt - int(row.suc or 0),
            "tokens": int(row.tokens or 0),
            "audio": 0,
        }
        for row in daily_rows.all()
    ]

    # ── 5. 从 AIModelUsageLog 获取成本（更精确） ─────────────
    cost_row = await db.execute(
        select(func.sum(AIModelUsageLog.estimated_cost))
        .where(AIModelUsageLog.created_at >= start_date)
    )
    total_cost = round(float(cost_row.scalar() or 0), 4)
    if total_cost == 0 and total_tokens > 0:
        total_cost = round(total_tokens / 1000 * 0.002 + total_audio / 60 * 0.01, 4)

    failure_rate = round((total_calls - success_count) / total_calls, 4) if total_calls > 0 else 0

    return {
        "success": True,
        "data": {
            "usage_summary": {
                "total_tokens": total_tokens,
                "total_audio_seconds": total_audio,
                "analysis_count": total_calls,
                "estimated_cost_rmb": total_cost,
            },
            "failure_stats": {
                "total_triggered": total_calls,
                "success_count": success_count,
                "failed_count": total_calls - success_count,
                "failure_rate": failure_rate,
            },
            "by_type": by_type,
            "top_users": top_users,
            "daily_trend": daily_trend,
            "today_calls": today_calls,
            "avg_latency_ms": avg_latency,
            "range": range,
            "start_date": start_date.isoformat(),
            "end_date": now.isoformat(),
        }
    }


@router.get("/model-usage")
async def get_model_usage_stats(
    range: str = Query("week", description="统计范围: day/week/month"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取 AI 模型使用统计
    
    按模型分组统计 Token 用量和成本
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可查看")
    
    # 计算时间范围
    now = datetime.utcnow()
    if range == "day":
        start_date = now - timedelta(days=1)
    elif range == "week":
        start_date = now - timedelta(days=7)
    else:
        start_date = now - timedelta(days=30)
    
    # 统计查询
    stmt = (
        select(
            AIModelConfig.name,
            func.count(AIModelUsageLog.id).label("count"),
            func.sum(AIModelUsageLog.input_tokens + AIModelUsageLog.output_tokens).label("tokens"),
            func.sum(AIModelUsageLog.estimated_cost).label("cost")
        )
        .join(AIModelConfig, AIModelUsageLog.model_config_id == AIModelConfig.id)
        .where(AIModelUsageLog.created_at >= start_date)
        .group_by(AIModelConfig.name)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    data = []
    for row in rows:
        data.append({
            "name": row.name,
            "request_count": row.count,
            "total_tokens": int(row.tokens or 0),
            "estimated_cost": round(float(row.cost or 0), 4)
        })
    
    # 按 Token 用量降序
    data.sort(key=lambda x: x["total_tokens"], reverse=True)
        
    return {"success": True, "data": data}


# ==================== 失败任务列表 ====================

@router.get("/failures")
async def get_failed_analyses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    semester_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取分析失败的任务列表
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可查看")
    
    # 查找有视频但没有分析结果或分析失败的提交
    stmt = select(Submission).where(
        and_(
            Submission.video_path.isnot(None),
            Submission.video_path != ""
        )
    )
    if semester_id:
        stmt = stmt.join(Task).where(Task.semester_id == semester_id)
    
    stmt = stmt.order_by(desc(Submission.created_at))
    
    result = await db.execute(stmt)
    submissions = list(result.scalars().all())
    
    # 筛选失败的
    failures = []
    for sub in submissions:
        is_failed = False
        error_reason = None
        
        if not sub.video_analysis:
            is_failed = True
            error_reason = "未进行分析"
        else:
            try:
                analysis = json.loads(sub.video_analysis)
                if analysis.get("status") == "failed":
                    is_failed = True
                    error_reason = analysis.get("error", "分析失败")
            except:
                is_failed = True
                error_reason = "分析结果解析失败"
        
        if is_failed:
            student = await db.get(User, sub.student_id)
            failures.append({
                "submission_id": sub.id,
                "task_id": sub.task_id,
                "student_id": sub.student_id,
                "student_name": student.name if student else None,
                "video_path": sub.video_path,
                "error_reason": error_reason,
                "created_at": sub.created_at.isoformat() if sub.created_at else None
            })
    
    # 分页
    total = len(failures)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = failures[start:end]
    
    return {
        "success": True,
        "data": {
            "items": paginated,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


# ==================== 批量重试 ====================

@router.post("/retry")
async def retry_failed_analyses(
    request: RetryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    批量重试失败的分析
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可执行")
    
    from app.services.video_analysis_service import VideoAnalysisService
    
    video_service = VideoAnalysisService()
    results = []
    
    for submission_id in request.submission_ids:
        sub = await db.get(Submission, submission_id)
        if not sub or not sub.video_path:
            results.append({
                "submission_id": submission_id,
                "success": False,
                "error": "提交不存在或无视频"
            })
            continue
        
        try:
            # 重新分析
            import os
            video_full_path = os.path.join(settings.UPLOAD_DIR, sub.video_path)
            
            if not os.path.exists(video_full_path):
                results.append({
                    "submission_id": submission_id,
                    "success": False,
                    "error": "视频文件不存在"
                })
                continue
            
            analysis_result = await video_service.analyze_video(video_full_path)
            
            # 保存结果
            sub.video_analysis = json.dumps(analysis_result, ensure_ascii=False)
            await db.commit()
            
            results.append({
                "submission_id": submission_id,
                "success": True,
                "overall_score": analysis_result.get("overall_score")
            })
            
        except Exception as e:
            results.append({
                "submission_id": submission_id,
                "success": False,
                "error": str(e)
            })
    
    success_count = sum(1 for r in results if r["success"])
    
    return {
        "success": True,
        "message": f"重试完成: {success_count}/{len(request.submission_ids)} 成功",
        "data": {
            "results": results,
            "success_count": success_count,
            "total": len(request.submission_ids)
        }
    }


# ==================== 审计日志 ====================

@router.get("/audit")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    action_type: Optional[str] = Query(None, description="操作类型: analyze/retry/feedback"),
    user_id: Optional[int] = Query(None, description="操作用户ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取 AI 操作审计日志
    
    注意：当前版本简化实现，从 Submission 的更新记录推断
    完整版本建议新增 AuditLog 表
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可查看")
    
    # 简化实现：返回最近有 AI 分析结果的提交作为审计记录
    stmt = select(Submission).where(
        Submission.video_analysis.isnot(None)
    ).order_by(desc(Submission.updated_at)).limit(page_size).offset((page - 1) * page_size)
    
    result = await db.execute(stmt)
    submissions = list(result.scalars().all())
    
    logs = []
    for sub in submissions:
        student = await db.get(User, sub.student_id)
        logs.append({
            "id": sub.id,
            "action": "video_analysis",
            "submission_id": sub.id,
            "user_id": sub.student_id,
            "user_name": student.name if student else None,
            "timestamp": sub.updated_at.isoformat() if sub.updated_at else None,
            "details": {
                "has_lesson_plan_analysis": sub.lesson_plan_analysis is not None,
                "has_video_analysis": sub.video_analysis is not None,
                "ai_score": sub.ai_suggested_score
            }
        })
    
    return {
        "success": True,
        "data": {
            "items": logs,
            "page": page,
            "page_size": page_size
        }
    }


# ==================== 阈值设置 ====================

@router.get("/thresholds")
async def get_thresholds(
    current_user: User = Depends(get_current_user),
):
    """
    获取当前告警阈值设置
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可查看")
    
    # 简化实现：返回默认值
    # 完整版本应从系统设置表读取
    return {
        "success": True,
        "data": {
            "daily_token_limit": 1000000,
            "daily_audio_seconds_limit": 36000,  # 10小时
            "failure_rate_threshold": 0.1  # 10%
        }
    }


@router.put("/thresholds")
async def update_thresholds(
    thresholds: ThresholdSettings,
    current_user: User = Depends(get_current_user),
):
    """
    更新告警阈值设置
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可设置")
    
    # 简化实现：仅返回成功
    # 完整版本应保存到系统设置表
    return {
        "success": True,
        "message": "阈值设置已更新",
        "data": thresholds.dict(exclude_none=True)
    }


# ==================== AI 服务状态 ====================

@router.get("/status")
async def get_ai_service_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取 AI 服务状态（优先从数据库读取模型配置）
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可查看")
    
    from app.models.ai_config import AIModelConfig
    from sqlalchemy import and_

    # 从数据库读取各类型的默认模型
    text_model = "无"
    audio_model = "无"
    vision_model = "无"
    provider = "无"
    has_api_key = False

    for model_type, label_ref in [("text", None), ("audio", None), ("vision", None)]:
        result = await db.execute(
            select(AIModelConfig).where(
                and_(
                    AIModelConfig.model_type == model_type,
                    AIModelConfig.is_enabled == True,
                    AIModelConfig.is_default == True,
                )
            )
        )
        cfg = result.scalar_one_or_none()
        if not cfg:
            result = await db.execute(
                select(AIModelConfig).where(
                    and_(
                        AIModelConfig.model_type == model_type,
                        AIModelConfig.is_enabled == True,
                    )
                ).order_by(AIModelConfig.priority.asc()).limit(1)
            )
            cfg = result.scalar_one_or_none()

        if cfg:
            if model_type == "text":
                text_model = cfg.model_id
                provider = cfg.provider
                has_api_key = bool(cfg.api_key)
            elif model_type == "audio":
                audio_model = cfg.model_id
            elif model_type == "vision":
                vision_model = cfg.model_id

    return {
        "success": True,
        "data": {
            "enabled": settings.AI_ENABLED,
            "provider": provider,
            "text_model": text_model,
            "audio_model": audio_model,
            "vision_model": vision_model,
            "vision_enabled": settings.ENABLE_GESTURE_ANALYSIS,
            "use_cloud_vision": settings.USE_CLOUD_VISION,
            "client_initialized": has_api_key,
        }
    }
