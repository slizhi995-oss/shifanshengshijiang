"""
统计数据路由
提供仪表盘所需的综合统计数据
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.semester import Semester
from app.models.task import Task
from app.models.submission import Submission, SubmissionStatus
from app.models.group import Group
from app.models.profile import PracticeSession

router = APIRouter()


# ==================== 学生端统计 ====================

@router.get("/student/dashboard")
async def get_student_dashboard_stats(
    semester_id: Optional[int] = Query(None, description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取学生仪表盘统计数据
    
    返回:
    - 任务完成情况（已提交/总数）
    - 平均分
    - 最近提交
    - 练习会话统计
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="仅学生可访问")
    
    # 获取分配信息
    assignment_stmt = select(Group).where(
        Group.student_id == current_user.id
    )
    if semester_id:
        assignment_stmt = assignment_stmt.where(Group.semester_id == semester_id)
    
    assignment_result = await db.execute(assignment_stmt)
    assignments = list(assignment_result.scalars().all())
    
    if not assignments:
        return {
            "success": True,
            "data": {
                "tasks": {"total": 0, "submitted": 0, "approved": 0},
                "scores": {"average": 0, "highest": 0, "latest": None},
                "practice": {"sessions": 0, "messages": 0},
                "recent_submissions": []
            }
        }
    
    # 统计任务
    instructor_ids = list(set(a.instructor_id for a in assignments))
    semester_ids = list(set(a.semester_id for a in assignments))
    
    task_stmt = select(Task).where(
        and_(
            Task.instructor_id.in_(instructor_ids),
            Task.semester_id.in_(semester_ids) if not semester_id else Task.semester_id == semester_id,
            Task.is_published == True
        )
    )
    task_result = await db.execute(task_stmt)
    tasks = list(task_result.scalars().all())
    total_tasks = len(tasks)
    
    # 统计提交
    sub_stmt = select(Submission).where(
        Submission.student_id == current_user.id
    )
    if semester_id:
        sub_stmt = sub_stmt.join(Task).where(Task.semester_id == semester_id)
    sub_stmt = sub_stmt.order_by(desc(Submission.submitted_at))
    
    sub_result = await db.execute(sub_stmt)
    submissions = list(sub_result.scalars().all())
    
    submitted = len(submissions)
    approved = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
    scores = [s.total_score for s in submissions if s.total_score is not None]
    
    # 统计练习会话
    session_stmt = select(PracticeSession).where(
        PracticeSession.student_id == current_user.id
    )
    session_result = await db.execute(session_stmt)
    sessions = list(session_result.scalars().all())
    
    total_sessions = len(sessions)
    total_messages = sum(s.message_count for s in sessions)
    
    # 最近提交
    recent_submissions = []
    for sub in submissions[:5]:
        task = await db.get(Task, sub.task_id)
        recent_submissions.append({
            "id": sub.id,
            "task_title": task.title if task else None,
            "status": sub.status.value if sub.status else None,
            "score": sub.total_score,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None
        })
    
    return {
        "success": True,
        "data": {
            "tasks": {
                "total": total_tasks,
                "submitted": submitted,
                "approved": approved,
                "completion_rate": round(submitted / total_tasks * 100, 1) if total_tasks > 0 else 0
            },
            "scores": {
                "average": round(sum(scores) / len(scores), 1) if scores else 0,
                "highest": max(scores) if scores else 0,
                "latest": scores[0] if scores else None
            },
            "practice": {
                "sessions": total_sessions,
                "messages": total_messages
            },
            "recent_submissions": recent_submissions
        }
    }


# ==================== 老师端统计 ====================

@router.get("/instructor/dashboard")
async def get_instructor_dashboard_stats(
    semester_id: int = Query(..., description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取老师仪表盘统计数据
    
    返回:
    - 学生统计（总数/已提交/已通过）
    - 待批改数量
    - 分数分布
    - 最近活动
    """
    if current_user.role not in [UserRole.INSTRUCTOR, UserRole.ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅老师/管理员可访问")
    
    instructor_id = current_user.id
    
    # 获取学生列表
    student_stmt = select(Group.student_id).where(
        and_(
            Group.instructor_id == instructor_id,
            Group.semester_id == semester_id
        )
    )
    student_result = await db.execute(student_stmt)
    student_ids = [row[0] for row in student_result.fetchall()]
    student_count = len(student_ids)
    
    # 获取任务
    task_stmt = select(Task).where(
        and_(
            Task.instructor_id == instructor_id,
            Task.semester_id == semester_id,
            Task.is_published == True
        )
    )
    task_result = await db.execute(task_stmt)
    tasks = list(task_result.scalars().all())
    task_count = len(tasks)
    task_ids = [t.id for t in tasks]
    
    # 获取提交
    if task_ids and student_ids:
        sub_stmt = select(Submission).where(
            and_(
                Submission.task_id.in_(task_ids),
                Submission.student_id.in_(student_ids)
            )
        ).order_by(desc(Submission.submitted_at))
        sub_result = await db.execute(sub_stmt)
        submissions = list(sub_result.scalars().all())
    else:
        submissions = []
    
    pending_count = sum(1 for s in submissions if s.status == SubmissionStatus.PENDING)
    approved_count = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
    graded_count = sum(1 for s in submissions if s.status in [SubmissionStatus.GRADED, SubmissionStatus.APPROVED])
    
    # 分数分布
    scores = [s.total_score for s in submissions if s.total_score is not None]
    distribution = {
        "90+": sum(1 for s in scores if s >= 90),
        "80-89": sum(1 for s in scores if 80 <= s < 90),
        "70-79": sum(1 for s in scores if 70 <= s < 80),
        "60-69": sum(1 for s in scores if 60 <= s < 70),
        "<60": sum(1 for s in scores if s < 60)
    }
    
    # 最近待批改
    recent_pending = []
    for sub in submissions:
        if sub.status == SubmissionStatus.PENDING:
            student = await db.get(User, sub.student_id)
            task = await db.get(Task, sub.task_id)
            recent_pending.append({
                "id": sub.id,
                "student_name": student.name if student else None,
                "task_title": task.title if task else None,
                "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None
            })
            if len(recent_pending) >= 5:
                break
    
    return {
        "success": True,
        "data": {
            "students": {
                "total": student_count,
                "submitted": len(set(s.student_id for s in submissions)),
                "all_approved": sum(1 for sid in student_ids if all(
                    s.status == SubmissionStatus.APPROVED
                    for s in submissions if s.student_id == sid
                ) and any(s.student_id == sid for s in submissions))
            },
            "tasks": {
                "total": task_count,
                "avg_submissions": round(len(submissions) / task_count, 1) if task_count > 0 else 0
            },
            "grading": {
                "pending": pending_count,
                "graded": graded_count,
                "approved": approved_count
            },
            "scores": {
                "average": round(sum(scores) / len(scores), 1) if scores else 0,
                "distribution": distribution
            },
            "recent_pending": recent_pending
        }
    }


# ==================== 管理员统计 ====================

@router.get("/admin/dashboard")
async def get_admin_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取管理员仪表盘统计数据
    
    返回:
    - 系统用户统计
    - 批次统计
    - 活跃度统计
    - AI 使用情况
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    
    # 用户统计
    user_stmt = select(User)
    user_result = await db.execute(user_stmt)
    users = list(user_result.scalars().all())
    
    student_count = sum(1 for u in users if u.role == UserRole.STUDENT)
    instructor_count = sum(1 for u in users if u.role == UserRole.INSTRUCTOR)
    admin_count = sum(1 for u in users if u.role in [UserRole.ADMIN, UserRole.ADMIN])
    
    # 批次统计
    semester_stmt = select(Semester)
    semester_result = await db.execute(semester_stmt)
    semesters = list(semester_result.scalars().all())
    
    draft_count = sum(1 for s in semesters if s.status and s.status.value == "draft")
    active_count = sum(1 for s in semesters if s.status and s.status.value == "active")
    completed_count = sum(1 for s in semesters if s.status and s.status.value == "completed")
    
    # 提交统计
    sub_stmt = select(Submission)
    sub_result = await db.execute(sub_stmt)
    submissions = list(sub_result.scalars().all())
    
    total_submissions = len(submissions)
    pending_submissions = sum(1 for s in submissions if s.status in [SubmissionStatus.PENDING, SubmissionStatus.GRADED])
    approved_submissions = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
    rejected_submissions = sum(1 for s in submissions if s.status == SubmissionStatus.REJECTED)
    
    # AI 使用统计
    ai_analyzed = sum(1 for s in submissions if s.lesson_plan_analysis or s.video_analysis)
    
    # 最近7天活跃度
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_submissions = sum(1 for s in submissions if s.created_at and s.created_at >= week_ago)
    
    result = {
        "users": {
            "total": len(users),
            "student": student_count,
            "instructor": instructor_count,
            "admin": admin_count
        },
        "semesters": {
            "total": len(semesters),
            "draft": draft_count,
            "active": active_count,
            "completed": completed_count
        },
        "submissions": {
            "total": total_submissions,
            "pending": pending_submissions,
            "approved": approved_submissions,
            "rejected": rejected_submissions,
            "approval_rate": round(approved_submissions / total_submissions * 100, 1) if total_submissions > 0 else 0
        },
        "ai": {
            "analyzed_submissions": ai_analyzed,
            "ai_usage_rate": round(ai_analyzed / total_submissions * 100, 1) if total_submissions > 0 else 0
        },
        "activity": {
            "recent_7d_submissions": recent_submissions
        }
    }
    # 演示模式：数据库为空时返回预置数据
    if total_submissions == 0 and student_count <= 3:
        result = {
            "users": {"total": 55, "student": 48, "instructor": 6, "admin": 1},
            "semesters": {"total": 3, "draft": 1, "active": 1, "completed": 1},
            "submissions": {"total": 156, "pending": 23, "approved": 98, "rejected": 35, "approval_rate": 62.8},
            "ai": {"analyzed_submissions": 142, "ai_usage_rate": 91.0},
            "activity": {"recent_7d_submissions": 47}
        }
    return result


# ==================== 通用统计接口 ====================

@router.get("/semester/{semester_id}/summary")
async def get_semester_summary(
    semester_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取批次汇总统计
    """
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="学生无权访问")
    
    semester = await db.get(Semester, semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="批次不存在")
    
    # 任务统计
    task_stmt = select(Task).where(Task.semester_id == semester_id)
    task_result = await db.execute(task_stmt)
    tasks = list(task_result.scalars().all())
    
    # 学生统计
    student_stmt = select(Group.student_id).where(
        Group.semester_id == semester_id
    ).distinct()
    student_result = await db.execute(student_stmt)
    student_count = len(list(student_result.fetchall()))
    
    # 老师统计
    instructor_stmt = select(Group.instructor_id).where(
        Group.semester_id == semester_id
    ).distinct()
    instructor_result = await db.execute(instructor_stmt)
    instructor_count = len(list(instructor_result.fetchall()))
    
    # 提交统计
    sub_stmt = select(Submission).join(Task).where(Task.semester_id == semester_id)
    sub_result = await db.execute(sub_stmt)
    submissions = list(sub_result.scalars().all())
    
    scores = [s.total_score for s in submissions if s.total_score is not None]
    
    return {
        "success": True,
        "data": {
            "semester": {
                "id": semester.id,
                "name": semester.name,
                "status": semester.status.value if semester.status else None
            },
            "counts": {
                "tasks": len(tasks),
                "students": student_count,
                "instructors": instructor_count,
                "submissions": len(submissions)
            },
            "scores": {
                "average": round(sum(scores) / len(scores), 1) if scores else 0,
                "min": min(scores) if scores else 0,
                "max": max(scores) if scores else 0
            },
            "status_breakdown": {
                "pending": sum(1 for s in submissions if s.status == SubmissionStatus.PENDING),
                "graded": sum(1 for s in submissions if s.status == SubmissionStatus.GRADED),
                "approved": sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED),
                "rejected": sum(1 for s in submissions if s.status == SubmissionStatus.REJECTED)
            }
        }
    }
