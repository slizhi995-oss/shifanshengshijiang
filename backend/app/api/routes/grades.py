"""
学生成绩管理API
提供学生成绩查询、统计功能，支持按批次、学院等条件筛选
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_instructor
from app.models.user import User, UserRole
from app.models.semester import Semester
from app.models.group import Group
from app.models.task import Task
from app.models.submission import Submission, SubmissionStatus

router = APIRouter()


@router.get(
    "/students",
    summary="获取学生成绩列表",
)
async def get_student_grades(
    semester_id: Optional[int] = Query(None, description="批次ID"),
    college: Optional[str] = Query(None, description="学院筛选"),
    major: Optional[str] = Query(None, description="专业筛选"),
    class_name: Optional[str] = Query(None, description="班级筛选"),
    keyword: Optional[str] = Query(None, description="搜索关键词（姓名/学号）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取学生成绩列表
    
    权限说明：
    - 超级管理员：可以查看所有学院的学生
    - 普通管理员：只能查看本学院的学生
    - 指导老师：只能查看自己指导的学生
    """
    # 构建基础查询
    query = select(User).where(
        User.role == UserRole.STUDENT,
        User.is_active == True,
    )
    
    # 权限过滤
    if current_user.role == UserRole.INSTRUCTOR:
        # 指导老师只能看自己指导的学生
        if not semester_id:
            raise HTTPException(status_code=400, detail="指导老师必须选择批次")
        
        # 获取该老师在该批次指导的学生ID
        groups_result = await db.execute(
            select(Group.student_id).where(
                Group.semester_id == semester_id,
                Group.instructor_id == current_user.id,
            )
        )
        student_ids = [row[0] for row in groups_result.fetchall()]
        if not student_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        
        query = query.where(User.id.in_(student_ids))
        
    elif current_user.role == UserRole.ADMIN and not current_user.is_super_admin:
        # 普通管理员只能看本学院的学生
        if not current_user.college:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        query = query.where(User.college == current_user.college)
    
    # 条件筛选
    if college:
        query = query.where(User.college == college)
    if major:
        query = query.where(User.major == major)
    if class_name:
        query = query.where(User.class_name == class_name)
    if keyword:
        query = query.where(
            or_(
                User.name.ilike(f"%{keyword}%"),
                User.user_code.ilike(f"%{keyword}%"),
            )
        )
    
    # 排序
    query = query.order_by(User.college, User.class_name, User.user_code)
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    students = result.scalars().all()
    
    # 如果选择了批次，获取每个学生的成绩数据
    student_data = []
    for student in students:
        student_info = {
            "id": student.id,
            "user_code": student.user_code,
            "name": student.name,
            "college": student.college,
            "major": student.major,
            "class_name": student.class_name,
            "instructor": None,
            "statistics": None,
        }
        
        if semester_id:
            # 获取指导老师
            group_result = await db.execute(
                select(Group).where(
                    Group.semester_id == semester_id,
                    Group.student_id == student.id,
                ).options(selectinload(Group.instructor))
            )
            group = group_result.scalar_one_or_none()
            if group and group.instructor:
                student_info["instructor"] = {
                    "id": group.instructor.id,
                    "name": group.instructor.name,
                }
            
            # 获取该学生在该批次的提交统计
            # 获取该学生导师发布的所有任务
            if group:
                tasks_result = await db.execute(
                    select(Task).where(
                        Task.semester_id == semester_id,
                        Task.instructor_id == group.instructor_id,
                        Task.is_published == True,
                    )
                )
                tasks = tasks_result.scalars().all()
                task_ids = [t.id for t in tasks]
                
                # 获取提交记录
                submissions_result = await db.execute(
                    select(Submission).where(
                        Submission.student_id == student.id,
                        Submission.task_id.in_(task_ids) if task_ids else False,
                    )
                )
                submissions = submissions_result.scalars().all()
                
                # 统计
                total_tasks = len(tasks)
                submitted = len(submissions)
                pending = sum(1 for s in submissions if s.status == SubmissionStatus.PENDING)
                approved = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
                rejected = sum(1 for s in submissions if s.status == SubmissionStatus.REJECTED)
                
                # 获取最终成绩（最新一次有成绩的提交）
                scored_submissions = [s for s in submissions if s.total_score is not None]
                final_score = None
                if scored_submissions:
                    # 按提交时间排序，取最新的
                    latest_submission = max(scored_submissions, key=lambda s: s.submitted_at or s.id)
                    final_score = latest_submission.total_score
                
                student_info["statistics"] = {
                    "total_tasks": total_tasks,
                    "submitted": submitted,
                    "pending": pending,
                    "approved": approved,
                    "rejected": rejected,
                    "not_submitted": total_tasks - submitted,
                    "final_score": final_score,  # 最终成绩
                    "completion_rate": round(approved / total_tasks * 100, 1) if total_tasks > 0 else 0,
                }
        
        student_data.append(student_info)
    
    return {
        "items": student_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get(
    "/students/{student_id}/detail",
    summary="获取学生详细成绩",
)
async def get_student_grade_detail(
    student_id: int,
    semester_id: int = Query(..., description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取学生在指定批次的详细成绩信息
    包括所有提交记录、文件、成绩等
    """
    # 获取学生信息
    student_result = await db.execute(
        select(User).where(User.id == student_id)
    )
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    # 权限检查
    if current_user.role == UserRole.INSTRUCTOR:
        # 检查是否是该学生的指导老师
        group_result = await db.execute(
            select(Group).where(
                Group.semester_id == semester_id,
                Group.student_id == student_id,
                Group.instructor_id == current_user.id,
            )
        )
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="您不是该学生的指导老师")
    
    elif current_user.role == UserRole.ADMIN and not current_user.is_super_admin:
        # 普通管理员只能看本学院的学生
        if student.college != current_user.college:
            raise HTTPException(status_code=403, detail="无权查看其他学院的学生")
    
    # 获取分组信息
    group_result = await db.execute(
        select(Group).where(
            Group.semester_id == semester_id,
            Group.student_id == student_id,
        ).options(selectinload(Group.instructor))
    )
    group = group_result.scalar_one_or_none()
    
    if not group:
        return {
            "student": {
                "id": student.id,
                "user_code": student.user_code,
                "name": student.name,
                "college": student.college,
                "major": student.major,
                "class_name": student.class_name,
            },
            "instructor": None,
            "submissions": [],
            "statistics": {
                "total_tasks": 0,
                "submitted": 0,
                "pending": 0,
                "approved": 0,
                "rejected": 0,
                "avg_score": None,
            }
        }
    
    # 获取该学生导师发布的所有任务
    tasks_result = await db.execute(
        select(Task).where(
            Task.semester_id == semester_id,
            Task.instructor_id == group.instructor_id,
            Task.is_published == True,
        ).options(selectinload(Task.instructor))
    )
    tasks = tasks_result.scalars().all()
    task_ids = [t.id for t in tasks]
    
    # 获取所有提交记录
    submissions_result = await db.execute(
        select(Submission).where(
            Submission.student_id == student_id,
            Submission.task_id.in_(task_ids) if task_ids else False,
        ).options(selectinload(Submission.task))
    )
    submissions = submissions_result.scalars().all()
    
    # 构建提交记录详情
    submission_details = []
    for sub in submissions:
        submission_details.append({
            "id": sub.id,
            "task_id": sub.task_id,
            "task_title": sub.task.title if sub.task else None,
            "task_description": sub.task.content if sub.task else None,
            "status": sub.status.value,
            "score": sub.total_score,
            "feedback": sub.feedback,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "reviewed_at": sub.reviewed_at.isoformat() if sub.reviewed_at else None,
            "lesson_plan_path": sub.lesson_plan_path,
            "lesson_plan_name": sub.lesson_plan_name,
            "video_path": sub.video_path,
            "video_name": sub.video_name,
        })
    
    # 统计信息
    total_tasks = len(tasks)
    submitted = len(submissions)
    pending = sum(1 for s in submissions if s.status == SubmissionStatus.PENDING)
    approved = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
    rejected = sum(1 for s in submissions if s.status == SubmissionStatus.REJECTED)
    
    scores = [s.total_score for s in submissions if s.total_score is not None]
    avg_score = sum(scores) / len(scores) if scores else None
    
    return {
        "student": {
            "id": student.id,
            "user_code": student.user_code,
            "name": student.name,
            "college": student.college,
            "major": student.major,
            "class_name": student.class_name,
        },
        "instructor": {
            "id": group.instructor.id,
            "name": group.instructor.name,
        } if group.instructor else None,
        "submissions": submission_details,
        "statistics": {
            "total_tasks": total_tasks,
            "submitted": submitted,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "not_submitted": total_tasks - submitted,
            "avg_score": round(avg_score, 2) if avg_score else None,
            "completion_rate": round(approved / total_tasks * 100, 1) if total_tasks > 0 else 0,
        }
    }


@router.get(
    "/filter-options",
    summary="获取筛选选项",
)
async def get_filter_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取可用的筛选选项（学院、专业、班级）
    根据用户权限返回不同的选项
    """
    # 构建基础查询
    query = select(User).where(
        User.role == UserRole.STUDENT,
        User.is_active == True,
    )
    
    # 权限过滤
    if current_user.role == UserRole.ADMIN and not current_user.is_super_admin:
        # 普通管理员只能看本学院
        if current_user.college:
            query = query.where(User.college == current_user.college)
    
    result = await db.execute(query)
    students = result.scalars().all()
    
    # 提取唯一值
    colleges = sorted(set(s.college for s in students if s.college))
    majors = sorted(set(s.major for s in students if s.major))
    classes = sorted(set(s.class_name for s in students if s.class_name))
    
    return {
        "colleges": colleges,
        "majors": majors,
        "classes": classes,
    }


@router.get(
    "/ai-insight",
    summary="AI 成绩洞察",
)
async def get_ai_insight(
    semester_id: int = Query(..., description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    AI 成绩洞察 - 返回该批次的整体统计分析数据
    包括：整体通过率、各班级对比、维度分析等
    """
    import json as _json

    # 获取该批次所有分组
    groups_result = await db.execute(
        select(Group).where(Group.semester_id == semester_id)
    )
    groups = groups_result.scalars().all()
    if not groups:
        return {"success": True, "data": None}

    student_ids = [g.student_id for g in groups]
    instructor_ids = list(set(g.instructor_id for g in groups))

    # 获取该批次的所有任务
    tasks_result = await db.execute(
        select(Task).where(
            Task.semester_id == semester_id,
            Task.is_published == True,
        )
    )
    tasks = tasks_result.scalars().all()
    task_ids = [t.id for t in tasks]

    if not task_ids:
        return {"success": True, "data": None}

    # 获取所有提交
    subs_result = await db.execute(
        select(Submission).where(
            Submission.task_id.in_(task_ids),
            Submission.student_id.in_(student_ids),
        )
    )
    submissions = subs_result.scalars().all()

    total_subs = len(submissions)
    approved = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
    pending = sum(1 for s in submissions if s.status == SubmissionStatus.PENDING)
    rejected = sum(1 for s in submissions if s.status == SubmissionStatus.REJECTED)
    scores = [s.total_score for s in submissions if s.total_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    pass_rate = round(approved / total_subs * 100, 1) if total_subs > 0 else 0

    # 班级对比
    student_result = await db.execute(
        select(User).where(User.id.in_(student_ids))
    )
    students_map = {s.id: s for s in student_result.scalars().all()}

    class_scores: dict = {}
    for sub in submissions:
        if sub.total_score is None:
            continue
        stu = students_map.get(sub.student_id)
        cls = stu.class_name if stu and stu.class_name else "未分班"
        if cls not in class_scores:
            class_scores[cls] = []
        class_scores[cls].append(sub.total_score)

    class_comparison = []
    for cls, sc_list in class_scores.items():
        class_comparison.append({
            "class_name": cls,
            "avg_score": round(sum(sc_list) / len(sc_list), 1),
            "count": len(sc_list),
        })
    class_comparison.sort(key=lambda x: x["avg_score"], reverse=True)

    # 维度分析 (从 lesson_plan_analysis JSON)
    dim_keys = ["structure", "objectives", "key_points", "teaching_process", "teaching_methods", "board_design"]
    dim_labels = ["教案设计", "教学目标", "知识讲解", "教学过程", "教学方法", "板书设计"]
    dim_sums = {k: 0.0 for k in dim_keys}
    dim_counts = {k: 0 for k in dim_keys}

    for sub in submissions:
        if not sub.lesson_plan_analysis:
            continue
        try:
            data = _json.loads(sub.lesson_plan_analysis)
            dims = data.get("dimensions", {})
            for k in dim_keys:
                score_val = None
                if isinstance(dims.get(k), dict):
                    score_val = dims[k].get("score")
                elif isinstance(dims.get(k), (int, float)):
                    score_val = dims[k]
                if score_val is not None:
                    dim_sums[k] += float(score_val)
                    dim_counts[k] += 1
        except Exception:
            continue

    dimensions = []
    weakest_dim = None
    weakest_score = 999
    for k, label in zip(dim_keys, dim_labels):
        avg = round(dim_sums[k] / dim_counts[k], 1) if dim_counts[k] > 0 else 0
        dimensions.append({"key": k, "label": label, "avg_score": avg, "count": dim_counts[k]})
        if avg > 0 and avg < weakest_score:
            weakest_score = avg
            weakest_dim = label

    return {
        "success": True,
        "data": {
            "total_students": len(student_ids),
            "total_submissions": total_subs,
            "approved": approved,
            "pending": pending,
            "rejected": rejected,
            "avg_score": avg_score,
            "pass_rate": pass_rate,
            "class_comparison": class_comparison[:10],
            "dimensions": dimensions,
            "weakest_dimension": weakest_dim,
            "score_distribution": {
                "excellent": sum(1 for s in scores if s >= 90),
                "good": sum(1 for s in scores if 80 <= s < 90),
                "medium": sum(1 for s in scores if 70 <= s < 80),
                "pass": sum(1 for s in scores if 60 <= s < 70),
                "fail": sum(1 for s in scores if s < 60),
            }
        }
    }
