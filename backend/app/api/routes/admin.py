"""
Admin API routes.
Global monitoring and statistics for administrators.
"""
import os
import uuid
import aiofiles
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from sqlalchemy import select, func, case, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User, UserRole
from app.models.semester import Semester
from app.models.group import Group
from app.models.task import Task
from app.models.submission import Submission, SubmissionStatus
from app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "/dashboard",
    summary="管理员仪表盘数据",
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """
    获取管理员仪表盘的统计数据。
    
    包括用户数量、批次状态、提交概况等。
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
    
    # 批次统计
    semester_stats = await db.execute(
        select(
            Semester.status,
            func.count(Semester.id).label("count")
        )
        .group_by(Semester.status)
    )
    semester_counts = {row.status.value: row.count for row in semester_stats.fetchall()}
    
    # 提交统计
    submission_stats = await db.execute(
        select(
            Submission.status,
            func.count(Submission.id).label("count")
        )
        .group_by(Submission.status)
    )
    submission_counts = {row.status.value: row.count for row in submission_stats.fetchall()}
    
    return {
        "users": {
            "total": sum(user_counts.values()),
            "admin": user_counts.get("admin", 0),
            "instructor": user_counts.get("instructor", 0),
            "student": user_counts.get("student", 0),
        },
        "semesters": {
            "total": sum(semester_counts.values()),
            "draft": semester_counts.get("draft", 0),
            "active": semester_counts.get("active", 0),
            "completed": semester_counts.get("completed", 0),
        },
        "submissions": {
            "total": sum(submission_counts.values()),
            "pending": submission_counts.get("pending", 0),
            "approved": submission_counts.get("approved", 0),
            "rejected": submission_counts.get("rejected", 0),
        },
    }


@router.get(
    "/monitor/{semester_id}",
    summary="全局监控学生提交状态",
)
async def monitor_submissions(
    semester_id: int,
    instructor_id: Optional[int] = Query(None, description="按老师筛选"),
    status_filter: Optional[SubmissionStatus] = Query(None, description="按状态筛选"),
    keyword: Optional[str] = Query(None, description="搜索学生姓名/学号"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """
    管理员全局监控所有学生的提交状态。
    
    权限说明：
    - 超级管理员：可以查看所有学院的学生
    - 普通管理员：只能查看本学院的学生
    
    支持按老师筛选、按状态筛选、搜索学生。
    """
    # 获取该批次所有分组
    groups_query = (
        select(Group)
        .where(Group.semester_id == semester_id)
        .options(
            selectinload(Group.student),
            selectinload(Group.instructor),
        )
    )
    
    if instructor_id:
        groups_query = groups_query.where(Group.instructor_id == instructor_id)
    
    groups_result = await db.execute(groups_query)
    groups = groups_result.scalars().all()
    
    # 权限过滤：普通管理员只能看本学院的学生
    if not current_user.is_super_admin and current_user.college:
        groups = [g for g in groups if g.student and g.student.college == current_user.college]
    
    # 获取该批次所有任务
    tasks_result = await db.execute(
        select(Task).where(
            Task.semester_id == semester_id,
            Task.is_published == True,
        )
    )
    tasks = tasks_result.scalars().all()
    task_ids = [t.id for t in tasks]
    
    # 获取所有提交
    submissions_result = await db.execute(
        select(Submission)
        .where(Submission.task_id.in_(task_ids) if task_ids else False)
        .options(selectinload(Submission.task))
    )
    submissions = submissions_result.scalars().all()
    
    # 按学生ID索引提交
    student_submissions = {}
    for sub in submissions:
        if sub.student_id not in student_submissions:
            student_submissions[sub.student_id] = []
        student_submissions[sub.student_id].append(sub)
    
    # 构建结果
    results = []
    for group in groups:
        student = group.student
        instructor = group.instructor
        
        # 搜索过滤
        if keyword:
            if keyword.lower() not in student.name.lower() and keyword.lower() not in student.user_code.lower():
                continue
        
        # 获取该学生的提交
        subs = student_submissions.get(student.id, [])
        
        # 统计
        pending = sum(1 for s in subs if s.status == SubmissionStatus.PENDING)
        approved = sum(1 for s in subs if s.status == SubmissionStatus.APPROVED)
        rejected = sum(1 for s in subs if s.status == SubmissionStatus.REJECTED)
        
        # 状态筛选
        if status_filter:
            if status_filter == SubmissionStatus.PENDING and pending == 0:
                continue
            elif status_filter == SubmissionStatus.APPROVED and approved == 0:
                continue
            elif status_filter == SubmissionStatus.REJECTED and rejected == 0:
                continue
        
        # 计算总任务数（该学生导师发布的任务）
        instructor_tasks = [t for t in tasks if t.instructor_id == instructor.id]
        total_tasks = len(instructor_tasks)

        # 构建该学生的提交明细，包含任务标题和文件路径，便于前端查看 PDF / 视频 等资料
        submission_details = [
            {
                "id": sub.id,
                "task_id": sub.task_id,
                "task_title": sub.task.title if sub.task else None,
                "status": sub.status.value,
                "submitted_at": sub.submitted_at,
                "lesson_plan_path": sub.lesson_plan_path,
                "lesson_plan_name": sub.lesson_plan_name,
                "video_path": sub.video_path,
                "video_name": sub.video_name,
            }
            for sub in subs
        ]

        results.append({
            "student": {
                "id": student.id,
                "user_code": student.user_code,
                "name": student.name,
                "college": student.college,
                "major": student.major,
                "class_name": student.class_name,
            },
            "instructor": {
                "id": instructor.id,
                "user_code": instructor.user_code,
                "name": instructor.name,
            },
            "stats": {
                "total_tasks": total_tasks,
                "submitted": len(subs),
                "pending": pending,
                "approved": approved,
                "rejected": rejected,
                "not_submitted": total_tasks - len(subs),
            },
            "submissions": submission_details,
        })
    
    # 分页
    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = results[start:end]
    
    return {
        "items": paginated,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get(
    "/instructors/{semester_id}",
    summary="获取批次中的指导老师列表",
)
async def get_semester_instructors(
    semester_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> List[dict]:
    """
    获取指定批次中有分配学生的指导老师列表。
    
    用于筛选下拉框。
    """
    result = await db.execute(
        select(
            User.id,
            User.user_code,
            User.name,
            func.count(Group.student_id).label("student_count")
        )
        .join(Group, Group.instructor_id == User.id)
        .where(Group.semester_id == semester_id)
        .group_by(User.id, User.user_code, User.name)
        .order_by(User.user_code)
    )
    
    instructors = []
    for row in result.fetchall():
        instructors.append({
            "id": row.id,
            "user_code": row.user_code,
            "name": row.name,
            "student_count": row.student_count,
        })
    
    return instructors


@router.get(
    "/submissions",
    summary="管理员获取所有提交（含学生和时段信息）",
)
async def get_all_submissions(
    semester_id: Optional[int] = Query(None, description="按试讲时段筛选"),
    keyword: Optional[str] = Query(None, description="按学生姓名/学号搜索"),
    status: Optional[SubmissionStatus] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """管理员查看所有学生的提交，支持按时段/状态/学生筛选。"""
    # 使用扁平 join 查询，避免 ORM 懒加载循环
    StudentUser = User.__table__.alias("su")
    base_conds = []
    if semester_id is not None:
        base_conds.append(Task.semester_id == semester_id)
    if keyword:
        base_conds.append(
            or_(
                StudentUser.c.name.ilike(f"%{keyword}%"),
                StudentUser.c.user_code.ilike(f"%{keyword}%"),
            )
        )
    if status is not None:
        base_conds.append(Submission.status == status)

    flat_select = (
        select(
            Submission.id,
            Submission.status,
            Submission.lesson_plan_path,
            Submission.lesson_plan_name,
            Submission.video_path,
            Submission.video_name,
            Submission.total_score,
            Submission.created_at,
            StudentUser.c.name.label("student_name"),
            StudentUser.c.user_code.label("student_code"),
            Semester.name.label("semester_name"),
            Task.title.label("task_title"),
        )
        .join(Task, Submission.task_id == Task.id)
        .join(Semester, Task.semester_id == Semester.id)
        .join(StudentUser, Submission.student_id == StudentUser.c.id)
    )
    if base_conds:
        flat_select = flat_select.where(*base_conds)

    total_result = await db.execute(
        select(func.count()).select_from(flat_select.subquery())
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        flat_select.order_by(Submission.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.mappings().all()

    items = [
        {
            "id": row["id"],
            "student_name": row["student_name"] or "",
            "student_code": row["student_code"] or "",
            "semester_name": row["semester_name"] or "",
            "task_title": row["task_title"] or "",
            "status": row["status"].value if row["status"] else "",
            "lesson_plan_path": row["lesson_plan_path"],
            "lesson_plan_name": row["lesson_plan_name"],
            "video_path": row["video_path"],
            "video_name": row["video_name"],
            "total_score": row["total_score"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post(
    "/materials/upload",
    summary="管理员上传参考材料",
)
async def upload_admin_material(
    title: str = Form(..., description="材料标题"),
    description: Optional[str] = Form(None, description="材料说明"),
    semester_id: Optional[int] = Form(None, description="关联试讲时段"),
    file: UploadFile = File(..., description="上传的文件"),
    _: User = Depends(require_admin),
) -> dict:
    """管理员上传参考材料（如评分标准、模板等），保存到服务器。"""
    upload_dir = os.path.join(settings.UPLOAD_DIR, "admin_materials")
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, unique_filename)
    async with aiofiles.open(file_path, "wb") as out_file:
        while content := await file.read(1024 * 1024):
            await out_file.write(content)
    return {
        "success": True,
        "title": title,
        "description": description,
        "semester_id": semester_id,
        "file_path": f"admin_materials/{unique_filename}",
        "file_name": file.filename,
    }


@router.get(
    "/export/{semester_id}",
    summary="导出批次成绩数据",
)
async def export_semester_grades(
    semester_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """
    导出指定批次的所有成绩数据。
    
    返回可用于生成Excel的结构化数据。
    """
    # 获取分组
    groups_result = await db.execute(
        select(Group)
        .where(Group.semester_id == semester_id)
        .options(
            selectinload(Group.student),
            selectinload(Group.instructor),
        )
    )
    groups = groups_result.scalars().all()
    
    # 获取任务
    tasks_result = await db.execute(
        select(Task)
        .where(Task.semester_id == semester_id)
        .order_by(Task.created_at)
    )
    tasks = tasks_result.scalars().all()
    
    # 获取提交
    task_ids = [t.id for t in tasks]
    submissions_result = await db.execute(
        select(Submission)
        .where(Submission.task_id.in_(task_ids) if task_ids else False)
    )
    submissions = submissions_result.scalars().all()
    
    # 构建提交索引
    sub_index = {}
    for sub in submissions:
        key = (sub.student_id, sub.task_id)
        sub_index[key] = sub
    
    # 构建导出数据
    export_data = []
    for group in groups:
        student = group.student
        instructor = group.instructor
        
        row = {
            "学号": student.user_code,
            "姓名": student.name,
            "指导老师": instructor.name,
        }
        
        # 添加每个任务的成绩
        for task in tasks:
            if task.instructor_id != instructor.id:
                continue
            
            sub = sub_index.get((student.id, task.id))
            if sub and sub.status == SubmissionStatus.APPROVED:
                row[f"{task.title}-教案分"] = sub.lesson_plan_score
                row[f"{task.title}-视频分"] = sub.video_score
                row[f"{task.title}-总分"] = sub.total_score
            else:
                row[f"{task.title}-教案分"] = None
                row[f"{task.title}-视频分"] = None
                row[f"{task.title}-总分"] = None
        
        export_data.append(row)
    
    return {
        "semester_id": semester_id,
        "data": export_data,
        "task_names": [t.title for t in tasks],
    }
