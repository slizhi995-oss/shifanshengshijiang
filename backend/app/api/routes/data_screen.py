"""
数据大屏 API
提供数据大屏页面所需的综合统计数据
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User, UserRole
from app.models.semester import Semester, SemesterStatus
from app.models.task import Task
from app.models.submission import Submission, SubmissionStatus
from app.models.group import Group
from app.models.ai_config import AIModelUsageLog

router = APIRouter()

# ==================== 演示模式：预置数据 ====================
_DEMO_OVERVIEW = {
    "totalStudents": 48,
    "totalInstructors": 6,
    "totalSubmissions": 156,
    "aiAnalysisCount": 312,
    "approvedSubmissions": 98,
    "pendingReviews": 23,
    "averageScore": 78.5,
    "completionRate": 62.8,
    "participatingStudents": 41,
    "participationRate": 85.4,
}

_DEMO_TRENDS = {
    "dates": [],  # 动态生成
    "submissions": [12, 18, 15, 22, 19, 25, 20],
    "approvals": [8, 14, 11, 18, 15, 21, 16],
}

_DEMO_DISTRIBUTION = [
    {"value": 15, "name": "优秀 (90-100)"},
    {"value": 32, "name": "良好 (80-89)"},
    {"value": 38, "name": "中等 (70-79)"},
    {"value": 14, "name": "及格 (60-69)"},
    {"value": 5, "name": "不及格 (<60)"},
]

_DEMO_RADAR = {
    "indicators": ["教案设计", "教学目标", "知识讲解", "教学过程", "教学方法", "板书设计"],
    "values": [76, 82, 71, 78, 68, 65],
    "count": 48,
}


@router.get("/overview")
async def get_data_screen_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    获取数据大屏概览数据
    
    返回:
    - 学生总数
    - 导师人数
    - 作业提交数
    - AI 分析次数
    - 已通过作业
    - 待批改数
    - 平均分数
    - 完成率
    """
    # 用户统计
    user_stats = await db.execute(
        select(
            User.role,
            func.count(User.id).label("count")
        )
        .where(User.is_active == True)
        .group_by(User.role)
    )
    user_counts = {row.role.value: row.count for row in user_stats.fetchall()}
    
    # 提交统计
    submission_stats = await db.execute(
        select(
            Submission.status,
            func.count(Submission.id).label("count")
        )
        .group_by(Submission.status)
    )
    submission_counts = {row.status.value: row.count for row in submission_stats.fetchall()}
    
    # 提交总数
    total_submissions = sum(submission_counts.values())
    pending_count = submission_counts.get("pending", 0)
    approved_count = submission_counts.get("approved", 0)
    
    # 平均分
    score_result = await db.execute(
        select(func.avg(Submission.total_score))
        .where(Submission.total_score.isnot(None))
    )
    avg_score = score_result.scalar() or 0
    
    # AI 使用统计 (来自使用日志)
    ai_usage_result = await db.execute(
        select(func.count(AIModelUsageLog.id))
    )
    ai_count = ai_usage_result.scalar() or 0
    
    # 完成率
    completion_rate = round((approved_count / total_submissions * 100), 1) if total_submissions > 0 else 0

    # 参与率：已提交过至少一次的学生数 / 总学生数
    participating_result = await db.execute(
        select(func.count(func.distinct(Submission.student_id)))
    )
    participating_students = participating_result.scalar() or 0
    total_students = user_counts.get("student", 0)
    participation_rate = round(
        min(100.0, participating_students / total_students * 100), 1
    ) if total_students > 0 else 0

    result = {
        "totalStudents": total_students,
        "totalInstructors": user_counts.get("instructor", 0),
        "totalSubmissions": total_submissions,
        "aiAnalysisCount": ai_count,
        "approvedSubmissions": approved_count,
        "pendingReviews": pending_count,
        "averageScore": round(avg_score, 1),
        "completionRate": completion_rate,
        "participatingStudents": participating_students,
        "participationRate": participation_rate,
    }
    # 演示模式：数据库为空时返回预置数据
    if total_submissions == 0 and total_students <= 3:
        return _DEMO_OVERVIEW
    return result


@router.get("/trends")
async def get_data_screen_trends(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    获取提交趋势数据
    
    Args:
        days: 统计天数，默认7天
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # 按日期统计提交数和通过数
    submissions_result = await db.execute(
        select(Submission)
        .where(Submission.created_at >= start_date)
        .order_by(Submission.created_at)
    )
    submissions = list(submissions_result.scalars().all())
    
    # 按日期分组
    from collections import defaultdict
    daily_submissions = defaultdict(int)
    daily_approvals = defaultdict(int)
    
    for sub in submissions:
        if sub.created_at:
            date_key = sub.created_at.strftime("%m-%d")
            daily_submissions[date_key] += 1
            if sub.status == SubmissionStatus.APPROVED:
                daily_approvals[date_key] += 1
    
    # 生成日期序列
    dates = []
    submissions_data = []
    approvals_data = []
    
    for i in range(days):
        date = start_date + timedelta(days=i)
        date_key = date.strftime("%m-%d")
        dates.append(date_key)
        submissions_data.append(daily_submissions.get(date_key, 0))
        approvals_data.append(daily_approvals.get(date_key, 0))
    
    result = {
        "dates": dates,
        "submissions": submissions_data,
        "approvals": approvals_data
    }
    # 演示模式：无提交数据时返回预置趋势
    if all(v == 0 for v in submissions_data):
        demo = dict(_DEMO_TRENDS)
        demo["dates"] = dates  # 用真实日期
        return demo
    return result


@router.get("/distribution")
async def get_score_distribution(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    获取成绩分布数据
    """
    scores_result = await db.execute(
        select(Submission.total_score)
        .where(Submission.total_score.isnot(None))
    )
    scores = [row[0] for row in scores_result.fetchall()]
    
    distribution = [
        {"value": sum(1 for s in scores if s >= 90), "name": "优秀 (90-100)"},
        {"value": sum(1 for s in scores if 80 <= s < 90), "name": "良好 (80-89)"},
        {"value": sum(1 for s in scores if 70 <= s < 80), "name": "中等 (70-79)"},
        {"value": sum(1 for s in scores if 60 <= s < 70), "name": "及格 (60-69)"},
        {"value": sum(1 for s in scores if s < 60), "name": "不及格 (<60)"}
    ]
    
    # 演示模式：无成绩数据时返回预置分布
    if all(d["value"] == 0 for d in distribution):
        return _DEMO_DISTRIBUTION
    return distribution


@router.get("/class-comparison")
async def get_class_comparison(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    获取班级平均分对比
    """
    # 按班级分组统计平均分
    result = await db.execute(
        select(
            User.class_name,
            func.avg(Submission.total_score).label("avg_score"),
            func.count(Submission.id).label("count")
        )
        .join(Submission, User.id == Submission.student_id)
        .where(
            User.class_name.isnot(None),
            Submission.total_score.isnot(None)
        )
        .group_by(User.class_name)
        .order_by(desc("avg_score"))
        .limit(10)
    )
    
    classes = []
    scores = []
    
    for row in result.fetchall():
        if row.class_name and row.count >= 1:
            classes.append(row.class_name[:6])  # 截断班级名称
            scores.append(round(row.avg_score, 1))
    
    return {
        "classes": classes or ["暂无数据"],
        "scores": scores or [0]
    }


@router.get("/ability-radar")
async def get_ability_radar(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    获取全校教学能力雷达图数据
    从 submission 的 lesson_plan_analysis JSON 字段中提取各维度评分的平均值
    """
    import json as _json

    result = await db.execute(
        select(Submission.lesson_plan_analysis)
        .where(Submission.lesson_plan_analysis.isnot(None))
    )
    analyses = result.scalars().all()

    # 维度映射
    dim_keys = ["structure", "objectives", "key_points", "teaching_process", "teaching_methods", "board_design"]
    dim_labels = ["教案设计", "教学目标", "知识讲解", "教学过程", "教学方法", "板书设计"]
    dim_sums = {k: 0.0 for k in dim_keys}
    dim_counts = {k: 0 for k in dim_keys}

    for raw in analyses:
        try:
            data = _json.loads(raw) if isinstance(raw, str) else raw
            dims = data.get("dimensions", {})
            for k in dim_keys:
                score = None
                if isinstance(dims.get(k), dict):
                    score = dims[k].get("score")
                elif isinstance(dims.get(k), (int, float)):
                    score = dims[k]
                if score is not None:
                    dim_sums[k] += float(score)
                    dim_counts[k] += 1
        except Exception:
            continue

    values = [
        round(dim_sums[k] / dim_counts[k], 1) if dim_counts[k] > 0 else 0
        for k in dim_keys
    ]

    result = {
        "indicators": dim_labels,
        "values": values,
        "count": max(dim_counts.values()) if dim_counts else 0,
    }
    # 演示模式：无雷达数据时返回预置数据
    if all(v == 0 for v in values):
        return _DEMO_RADAR
    return result


@router.get("/ai-logs")
async def get_ai_logs(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    获取最近的 AI 调用日志，用于数据大屏实时动态展示
    """
    usage_type_labels = {
        "lesson_plan_analysis": "教案分析完成",
        "video_analysis": "视频分析处理",
        "chat": "AI 备课助手会话",
        "feedback": "评语生成完成",
        "summary": "教案摘要生成",
        "improve": "改进建议生成",
        "generate": "AI 教案生成",
        "auto_grade": "AI 智能批改",
        "pre_check": "预提交质量检测",
        "data_narrative": "数据叙事生成",
        "alert_analysis": "AI 预警分析",
    }

    result = await db.execute(
        select(AIModelUsageLog)
        .order_by(desc(AIModelUsageLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()

    items = []
    for log in logs:
        created = log.created_at
        time_str = created.strftime("%H:%M:%S") if created else "00:00:00"
        action = usage_type_labels.get(log.usage_type, log.usage_type)
        status = "success" if log.is_success else "processing"
        items.append({"time": time_str, "action": action, "status": status})

    return items
