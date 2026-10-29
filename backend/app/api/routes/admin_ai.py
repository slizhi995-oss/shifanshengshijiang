"""
管理员 AI 功能路由 - AI预警中心、智能分配
"""
import logging
import json, re
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.core.config import settings
from app.core.deps import require_admin, get_current_user, get_db
from app.models.user import User
from app.models.submission import Submission, SubmissionStatus
from app.models.group import Group
from app.models.ai_config import AIModelConfig
from app.services.ai_model_service import get_dynamic_ai_service

logger = logging.getLogger(__name__)

router = APIRouter()

# 空数据响应模板，任何异常均返回此结构，绝不 500
_EMPTY_ALERTS_RESPONSE = {
    "success": True,
    "data": {
        "alerts": [],
        "total": 0,
        "danger_count": 0,
        "warning_count": 0,
    },
}


@router.get("/ai-alerts")
async def get_ai_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """AI 预警中心 - 自动检测系统异常（仅管理员可访问）"""
    try:
        alerts: list = []
        now = datetime.utcnow()

        # 1. 检测长期不活跃学生（基于 updated_at，无 last_login_at 字段）
        try:
            seven_days_ago = now - timedelta(days=7)
            inactive_result = await db.execute(
                select(User).where(
                    User.role == "student",
                    User.is_active == True,
                    User.updated_at < seven_days_ago,
                )
            )
            inactive_students = inactive_result.scalars().all()
            if inactive_students:
                alerts.append({
                    "id": "inactive_students",
                    "level": "warning",
                    "title": "学生活跃度异常",
                    "message": f"{len(inactive_students)}名学生超过7天无活跃记录",
                    "details": [{"id": s.id, "name": s.name, "user_code": s.user_code} for s in inactive_students[:10]],
                    "action": "建议联系导师关注这些学生的学习情况",
                    "count": len(inactive_students),
                })
        except Exception as e:
            logger.warning(f"[ai-alerts] 检测不活跃学生失败: {e}")

        # 2. 检测超过3天未批改的提交
        try:
            three_days_ago = now - timedelta(days=3)
            pending_result = await db.execute(
                select(func.count(Submission.id)).where(
                    Submission.status == "pending",
                    Submission.submitted_at < three_days_ago,
                )
            )
            pending_count = pending_result.scalar() or 0
            if pending_count > 0:
                alerts.append({
                    "id": "pending_reviews",
                    "level": "danger",
                    "title": "批改进度滞后",
                    "message": f"{pending_count}份作业已提交超过3天仍未批改",
                    "details": [],
                    "action": "建议提醒导师尽快完成批改",
                    "count": pending_count,
                })
        except Exception as e:
            logger.warning(f"[ai-alerts] 检测待批改提交失败: {e}")

        # 3. 检测AI服务状态
        try:
            ai_status_level = "info"
            ai_status_msg = ""
            if not settings.AI_ENABLED:
                ai_status_level = "danger"
                ai_status_msg = "AI功能未启用，所有AI分析功能不可用"
            else:
                model_result = await db.execute(
                    select(func.count(AIModelConfig.id)).where(AIModelConfig.is_enabled == True)
                )
                enabled_count = model_result.scalar() or 0
                if enabled_count == 0:
                    ai_status_level = "danger"
                    ai_status_msg = "没有启用的AI模型，AI功能将无法使用"
                else:
                    ai_status_level = "success"
                    ai_status_msg = f"{enabled_count}个AI模型正常运行"

            alerts.append({
                "id": "ai_service",
                "level": ai_status_level,
                "title": "AI服务健康度",
                "message": ai_status_msg,
                "details": [],
                "action": "前往AI运营看板查看详情" if ai_status_level != "success" else "",
                "count": 0,
            })
        except Exception as e:
            logger.warning(f"[ai-alerts] 检测AI服务状态失败: {e}")

        # 4. 检测导师工作负载不均
        try:
            load_result = await db.execute(
                select(Group.instructor_id, func.count(Group.id).label("cnt"))
                .group_by(Group.instructor_id)
            )
            loads = list(load_result)
            if loads:
                counts = [r[1] for r in loads]
                max_load = max(counts)
                min_load = min(counts)
                if max_load > 0 and max_load - min_load > max_load * 0.5:
                    alerts.append({
                        "id": "workload_imbalance",
                        "level": "warning",
                        "title": "导师负载不均",
                        "message": f"导师学生数差异较大（最多{max_load}人，最少{min_load}人）",
                        "details": [],
                        "action": "建议使用AI智能分配重新平衡",
                        "count": 0,
                    })
        except Exception as e:
            logger.warning(f"[ai-alerts] 检测导师负载失败: {e}")

        # 5. 统计被驳回的提交
        try:
            rejected_result = await db.execute(
                select(func.count(Submission.id)).where(
                    Submission.status == "rejected",
                    Submission.updated_at > (now - timedelta(days=7)),
                )
            )
            rejected_count = rejected_result.scalar() or 0
            if rejected_count > 5:
                alerts.append({
                    "id": "high_rejection",
                    "level": "warning",
                    "title": "驳回率偏高",
                    "message": f"近7天有{rejected_count}份作业被驳回",
                    "details": [],
                    "action": "建议检查学生是否理解作业要求",
                    "count": rejected_count,
                })
        except Exception as e:
            logger.warning(f"[ai-alerts] 检测驳回率失败: {e}")

        # 6. 检测未分配导师的学生
        try:
            all_student_count_result = await db.execute(
                select(func.count(User.id)).where(User.role == "student", User.is_active == True)
            )
            total_students = all_student_count_result.scalar() or 0

            assigned_count_result = await db.execute(
                select(func.count(func.distinct(Group.student_id)))
            )
            assigned_students = assigned_count_result.scalar() or 0

            unassigned = total_students - assigned_students
            if unassigned > 0:
                alerts.append({
                    "id": "unassigned_students",
                    "level": "warning",
                    "title": "学生未分配导师",
                    "message": f"{unassigned}名学生尚未分配指导老师",
                    "details": [],
                    "action": "前往分组分配进行分配，或使用AI智能分配",
                    "count": unassigned,
                })
        except Exception as e:
            logger.warning(f"[ai-alerts] 检测未分配学生失败: {e}")

        # Sort: danger first, then warning, then info
        level_order = {"danger": 0, "warning": 1, "info": 2, "success": 3}
        alerts.sort(key=lambda a: level_order.get(a["level"], 9))

        return {
            "success": True,
            "data": {
                "alerts": alerts,
                "total": len(alerts),
                "danger_count": sum(1 for a in alerts if a["level"] == "danger"),
                "warning_count": sum(1 for a in alerts if a["level"] == "warning"),
            },
        }

    except Exception as e:
        logger.error(f"[ai-alerts] 获取AI预警数据时发生顶层异常: {e}", exc_info=True)
        return _EMPTY_ALERTS_RESPONSE


class AIAlertAnalysisRequest(BaseModel):
    """AI 预警智能分析请求"""
    alerts: list = Field(default_factory=list, description="当前预警数据列表")
    model_id: Optional[int] = Field(None, description="指定使用的AI模型ID")


@router.post("/ai-alerts/analysis")
async def ai_alert_analysis(
    request: AIAlertAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """AI 预警智能分析 - 调用 AI 模型对预警数据进行深度诊断和建议生成"""
    try:
        if not settings.AI_ENABLED:
            return {"success": False, "message": "AI功能未启用"}

        ai_service = await get_dynamic_ai_service(db, model_id=request.model_id)

        alerts_summary = json.dumps(request.alerts, ensure_ascii=False, default=str)

        prompt = f"""你是一个教育管理AI助手，请对以下试讲管理系统的预警数据进行深度智能分析。

当前预警数据:
{alerts_summary}

请用中文输出，严格按以下JSON格式返回（不要markdown代码块包裹）:
{{
  "overall_risk": "high/medium/low",
  "risk_score": 0-100的整数(100为最安全),
  "diagnosis": "一段50-100字的AI整体诊断摘要，要像AI分析师一样专业",
  "recommendations": [
    {{
      "alert_id": "对应预警的id",
      "ai_suggestion": "AI针对此预警的智能建议(30-60字)",
      "urgency": "high/medium/low",
      "predicted_impact": "如不处理可能的影响(20-40字)"
    }}
  ],
  "trend_prediction": "AI对未来7天系统风险趋势的预测(30-50字)"
}}"""

        result = await ai_service.chat_completion(
            messages=[
                {"role": "system", "content": "你是教育管理系统的AI预警分析引擎，擅长从数据中发现潜在风险并给出专业建议。"},
                {"role": "user", "content": prompt},
            ],
            user_id=current_user.id,
            model_id=request.model_id,
            usage_type="alert_analysis",
            temperature=0.6,
        )

        # 尝试解析 JSON
        try:
            # 尝试直接解析
            analysis = json.loads(result.strip())
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                analysis = {
                    "overall_risk": "medium",
                    "risk_score": 70,
                    "diagnosis": result.strip()[:200],
                    "recommendations": [],
                    "trend_prediction": "数据不足，暂无法预测趋势。"
                }

        return {"success": True, "data": analysis}

    except Exception as e:
        logger.error(f"[ai-alerts] AI分析失败: {e}", exc_info=True)
        return {"success": False, "message": f"AI分析失败: {str(e)}"}


class AIAssignmentRequest(BaseModel):
    """AI智能分配请求"""
    semester_id: int = Field(..., description="批次ID")
    instructor_ids: List[int] = Field(..., description="参与分配的导师ID列表")
    model_id: Optional[int] = Field(None, description="AI模型ID")


@router.post("/ai-assignment")
async def ai_smart_assignment(
    request: AIAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 智能分配 - 根据导师负载和学生需求推荐最优分配方案"""
    # 获取未分配的学生
    assigned_result = await db.execute(
        select(Group.student_id).where(Group.semester_id == request.semester_id)
    )
    assigned_ids = set(r[0] for r in assigned_result)

    all_students_result = await db.execute(
        select(User).where(User.role == "student", User.is_active == True)
    )
    all_students = all_students_result.scalars().all()
    unassigned = [s for s in all_students if s.id not in assigned_ids]

    if not unassigned:
        return {"success": True, "data": {"message": "没有未分配的学生", "assignments": []}}

    # 获取导师信息和当前负载
    instructor_result = await db.execute(
        select(User).where(User.id.in_(request.instructor_ids))
    )
    instructors = instructor_result.scalars().all()

    load_result = await db.execute(
        select(Group.instructor_id, func.count(Group.id).label("cnt"))
        .where(Group.semester_id == request.semester_id, Group.instructor_id.in_(request.instructor_ids))
        .group_by(Group.instructor_id)
    )
    current_loads = {r[0]: r[1] for r in load_result}

    # 简单均衡分配算法
    total_to_assign = len(unassigned)
    num_instructors = len(instructors)
    if num_instructors == 0:
        raise HTTPException(status_code=400, detail="请选择至少一位导师")

    # 计算每位导师应分配的学生数（考虑已有负载）
    assignments = []
    instructor_quotas = []
    for inst in instructors:
        current = current_loads.get(inst.id, 0)
        instructor_quotas.append({"instructor": inst, "current": current, "new": 0, "students": []})

    # 按当前负载从少到多排序，优先分配给负载少的导师
    import random
    shuffled_students = list(unassigned)
    random.shuffle(shuffled_students)

    for student in shuffled_students:
        # 选择当前总负载最少的导师
        instructor_quotas.sort(key=lambda x: x["current"] + x["new"])
        target = instructor_quotas[0]
        target["new"] += 1
        target["students"].append({
            "id": student.id, "name": student.name,
            "user_code": student.user_code, "college": student.college or "",
            "major": student.major or "", "class_name": student.class_name or "",
        })

    for q in instructor_quotas:
        if q["students"]:
            assignments.append({
                "instructor_id": q["instructor"].id,
                "instructor_name": q["instructor"].name,
                "current_students": q["current"],
                "new_students": q["new"],
                "total_after": q["current"] + q["new"],
                "students": q["students"],
                "reason": f"当前{q['current']}名学生，新分配{q['new']}名，实现负载均衡"
            })

    return {"success": True, "data": {
        "total_unassigned": total_to_assign,
        "total_instructors": num_instructors,
        "assignments": assignments,
        "balance_score": round(100 - (max(q["current"] + q["new"] for q in instructor_quotas) -
                                       min(q["current"] + q["new"] for q in instructor_quotas)) * 5, 1)
                         if instructor_quotas else 100,
    }}


# ==================== AI 公告撰写助手 ====================

class AINoticeDraftRequest(BaseModel):
    """AI 公告草稿生成请求"""
    key_points: str = Field(..., description="公告要点/关键信息")
    tone: str = Field(default="formal", description="语气: formal/friendly/urgent")
    model_id: Optional[int] = Field(None, description="AI模型ID")


@router.post("/ai-notice-draft")
async def generate_notice_draft(
    request: AINoticeDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """AI 智能生成公告草稿"""
    try:
        if not settings.AI_ENABLED:
            return {"success": False, "message": "AI功能未启用"}

        ai_service = await get_dynamic_ai_service(db, model_id=request.model_id)

        tone_map = {
            "formal": "正式、专业",
            "friendly": "友好、亲切",
            "urgent": "紧急、严肃",
        }
        tone_desc = tone_map.get(request.tone, "正式、专业")

        prompt = f"""你是一个高校师范生试讲管理系统的公告撰写助手。
请根据以下要点，生成一篇{tone_desc}风格的公告内容。

要点：
{request.key_points}

要求：
1. 语言流畅、{tone_desc}
2. 结构清晰，必要时使用分点说明
3. 直接输出公告正文（不要输出标题，标题由管理员自行填写）
4. 适当增加呼吁或提醒语句
5. 长度控制在100-300字"""

        result = await ai_service.chat_completion(
            messages=[
                {"role": "system", "content": "你是高校教务公告撰写助手，擅长生成规范的教务公告。"},
                {"role": "user", "content": prompt},
            ],
            user_id=current_user.id,
            model_id=request.model_id,
            usage_type="notice_draft",
            temperature=0.7,
        )

        return {"success": True, "data": {"content": result.strip()}}

    except Exception as e:
        logger.error(f"[ai-notice-draft] AI生成公告失败: {e}", exc_info=True)
        return {"success": False, "message": f"AI生成失败: {str(e)}"}


# ==================== AI 批次总结报告 ====================

@router.get("/semester-summary/{semester_id}")
async def get_semester_ai_summary(
    semester_id: int,
    model_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """AI 生成批次总结报告"""
    from app.models.semester import Semester
    from app.models.task import Task

    try:
        # 获取批次信息
        sem_result = await db.execute(select(Semester).where(Semester.id == semester_id))
        semester = sem_result.scalar_one_or_none()
        if not semester:
            return {"success": False, "message": "批次不存在"}

        # 获取该批次统计数据
        groups_result = await db.execute(
            select(Group).where(Group.semester_id == semester_id)
        )
        groups = list(groups_result.scalars().all())
        student_ids = [g.student_id for g in groups]
        instructor_ids = list(set(g.instructor_id for g in groups))

        tasks_result = await db.execute(
            select(Task).where(Task.semester_id == semester_id, Task.is_published == True)
        )
        tasks = list(tasks_result.scalars().all())
        task_ids = [t.id for t in tasks]

        subs_result = await db.execute(
            select(Submission).where(
                Submission.task_id.in_(task_ids) if task_ids else False,
            )
        )
        submissions = list(subs_result.scalars().all())

        total_subs = len(submissions)
        approved = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
        rejected = sum(1 for s in submissions if s.status == SubmissionStatus.REJECTED)
        scores = [s.total_score for s in submissions if s.total_score is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        pass_rate = round(approved / total_subs * 100, 1) if total_subs > 0 else 0

        stats_summary = {
            "semester_name": semester.name,
            "status": semester.status.value if hasattr(semester.status, 'value') else str(semester.status),
            "total_students": len(student_ids),
            "total_instructors": len(instructor_ids),
            "total_tasks": len(tasks),
            "total_submissions": total_subs,
            "approved": approved,
            "rejected": rejected,
            "avg_score": avg_score,
            "pass_rate": pass_rate,
            "score_range": f"{min(scores):.0f}-{max(scores):.0f}" if scores else "N/A",
        }

        if not settings.AI_ENABLED:
            return {"success": True, "data": {"stats": stats_summary, "ai_summary": None}}

        ai_service = await get_dynamic_ai_service(db, model_id=model_id)

        prompt = f"""你是一个教育管理AI助手，请对以下试讲批次的数据进行总结分析。

批次数据:
{json.dumps(stats_summary, ensure_ascii=False)}

请生成一份200-400字的批次总结报告，包含：
1. 总体评价（一句话概括）
2. 数据亮点
3. 存在的问题
4. 改进建议

直接输出中文报告正文，不要使用JSON格式。"""

        result = await ai_service.chat_completion(
            messages=[
                {"role": "system", "content": "你是教育管理分析专家，擅长从数据中提炼教学质量洞察。"},
                {"role": "user", "content": prompt},
            ],
            user_id=current_user.id,
            model_id=model_id,
            usage_type="semester_summary",
            temperature=0.6,
        )

        return {"success": True, "data": {"stats": stats_summary, "ai_summary": result.strip()}}

    except Exception as e:
        logger.error(f"[semester-summary] 生成批次总结失败: {e}", exc_info=True)
        return {"success": False, "message": f"生成失败: {str(e)}"}
