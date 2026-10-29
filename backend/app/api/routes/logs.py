"""
系统日志路由
管理员查看操作日志 —从多个真实表合并生成
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User, UserRole
from app.models.submission import Submission, SubmissionStatus
from app.models.task import Task
from app.models.rubric import AICallLog

router = APIRouter()


AI_CALL_TYPE_MAP = {
    "analyze": "教案分析", "summary": "教案摘要", "improve": "改进建议",
    "feedback": "生成评语", "generate": "教案生成", "video_analyze": "视频分析",
    "chat": "AI 对话", "knowledge_graph": "知识图谱", "profile": "画像生成",
    "batch_analyze": "批量分析",
}


async def _build_all_logs(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    从多个真实表合并生成日志条目列表（按 created_at 降序）
    """
    logs: List[Dict[str, Any]] = []

    # ── 1. 作业提交日志 ──────────────────────────────────────────
    sub_result = await db.execute(
        select(Submission, User)
        .join(User, Submission.student_id == User.id, isouter=True)
        .order_by(desc(Submission.created_at))
        .limit(500)
    )
    for row in sub_result.all():
        sub, user = row[0], row[1]
        if sub.status == SubmissionStatus.APPROVED:
            action, detail = "approve", f"教案/视频提交已通过 (ID:{sub.id})，得分:{sub.total_score or '-'}"
        elif sub.status == SubmissionStatus.REJECTED:
            action, detail = "reject", f"教案/视频提交被驳回 (ID:{sub.id})"
        else:
            action, detail = "create", f"提交教案/视频 (ID:{sub.id})"
        logs.append({
            "_ts": sub.created_at,
            "module": "submission",
            "action": action,
            "user_name": user.name if user else "学生",
            "user_code": user.user_code if user else "-",
            "ip": "-",
            "detail": detail,
        })
        # 评分时间单独记一条
        if sub.reviewed_at and sub.total_score is not None:
            logs.append({
                "_ts": sub.reviewed_at,
                "module": "grade",
                "action": "approve" if sub.status == SubmissionStatus.APPROVED else "update",
                "user_name": "教师",
                "user_code": "TEACHER",
                "ip": "-",
                "detail": f"批改完成 (提交ID:{sub.id})，得分:{sub.total_score}",
            })

    # ── 2. 任务管理日志 ──────────────────────────────────────────
    task_result = await db.execute(
        select(Task, User)
        .join(User, Task.instructor_id == User.id, isouter=True)
        .order_by(desc(Task.created_at))
        .limit(200)
    )
    for row in task_result.all():
        task, user = row[0], row[1]
        logs.append({
            "_ts": task.created_at,
            "module": "task",
            "action": "create",
            "user_name": user.name if user else "教师",
            "user_code": user.user_code if user else "-",
            "ip": "-",
            "detail": f"发布试讲任务：{task.title}",
        })

    # ── 3. 用户注册日志 ──────────────────────────────────────────
    user_result = await db.execute(
        select(User).order_by(desc(User.created_at)).limit(200)
    )
    for user in user_result.scalars().all():
        if user.created_at:
            role_label = {"admin": "管理员", "instructor": "教师", "student": "学生"}.get(
                user.role.value if user.role else "", "用户"
            )
            logs.append({
                "_ts": user.created_at,
                "module": "user",
                "action": "create",
                "user_name": user.name or user.user_code,
                "user_code": user.user_code,
                "ip": "-",
                "detail": f"新{role_label}账号创建：{user.name or user.user_code} ({user.user_code})",
            })

    # ── 4. AI 调用日志 ──────────────────────────────────────────
    ai_result = await db.execute(
        select(AICallLog, User)
        .join(User, AICallLog.user_id == User.id, isouter=True)
        .order_by(desc(AICallLog.created_at))
        .limit(500)
    )
    for row in ai_result.all():
        log, user = row[0], row[1]
        type_label = AI_CALL_TYPE_MAP.get(log.call_type, log.call_type)
        logs.append({
            "_ts": log.created_at,
            "module": "ai",
            "action": "create" if log.is_success else "error",
            "user_name": user.name if user else "系统",
            "user_code": user.user_code if user else "SYSTEM",
            "ip": log.ip_address or "-",
            "detail": f"{type_label}{'成功' if log.is_success else '失败'}"
                      f" | {log.provider}/{log.model}"
                      f" | tokens:{log.total_tokens} | {log.latency_ms}ms"
                      + (f" | 错误:{log.error_message[:60]}" if log.error_message else ""),
        })

    # 按时间倒序排列
    logs.sort(key=lambda x: x["_ts"] or datetime.min, reverse=True)

    # 注入自增 id 并移除内部时间戳
    for i, entry in enumerate(logs):
        ts = entry.pop("_ts")
        entry["id"] = i + 1
        entry["created_at"] = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ""

    return logs


@router.get("/logs")
async def get_system_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    获取系统日志（从多个真实表合并生成）
    """
    all_logs = await _build_all_logs(db)

    # 过滤
    if module:
        all_logs = [l for l in all_logs if l["module"] == module]
    if action:
        all_logs = [l for l in all_logs if l["action"] == action]
    if user_id:
        all_logs = [l for l in all_logs if l["user_code"] == user_id or str(user_id) in l["user_code"]]
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            all_logs = [l for l in all_logs if l["created_at"] >= sd.strftime("%Y-%m-%d")]
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            all_logs = [l for l in all_logs if l["created_at"] <= ed.strftime("%Y-%m-%d 23:59:59")]
        except ValueError:
            pass

    total = len(all_logs)
    start = (page - 1) * page_size
    items = all_logs[start: start + page_size]

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@router.get("/logs/statistics")
async def get_log_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    获取日志统计（基于真实数据）
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # 今日提交数
    today_subs = await db.execute(
        select(func.count(Submission.id))
        .where(Submission.created_at >= today_start)
    )
    # 今日批改数
    today_grades = await db.execute(
        select(func.count(Submission.id))
        .where(and_(
            Submission.reviewed_at >= today_start,
            Submission.total_score.isnot(None)
        ))
    )
    # 总用户数
    total_users = await db.execute(select(func.count(User.id)))
    # AI 调用总数
    total_ai = await db.execute(select(func.count(AICallLog.id)))

    return {
        "success": True,
        "data": {
            "today_submissions": today_subs.scalar() or 0,
            "today_grades": today_grades.scalar() or 0,
            "total_users": total_users.scalar() or 0,
            "total_ai_calls": total_ai.scalar() or 0,
        }
    }
