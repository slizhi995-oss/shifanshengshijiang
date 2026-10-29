"""
Task management API routes.
Handles instructor task/requirement publishing.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_instructor
from app.models.user import User, UserRole
from app.models.semester import Semester
from app.models.task import Task
from app.models.group import Group
from app.models.submission import Submission, SubmissionStatus
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse

router = APIRouter()


@router.get(
    "",
    response_model=List[TaskResponse],
    summary="获取任务列表",
)
async def get_tasks(
    semester_id: int = Query(..., description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TaskResponse]:
    """
    获取指定批次的任务列表。
    
    - 管理员：查看所有任务
    - 老师：查看自己发布的任务
    - 学生：查看自己导师发布的已发布任务
    """
    query = select(Task).where(Task.semester_id == semester_id)
    
    if current_user.role == UserRole.INSTRUCTOR:
        query = query.where(Task.instructor_id == current_user.id)
    elif current_user.role == UserRole.STUDENT:
        # 获取学生的导师
        group_result = await db.execute(
            select(Group).where(
                Group.semester_id == semester_id,
                Group.student_id == current_user.id,
            )
        )
        group = group_result.scalar_one_or_none()
        if not group:
            return []
        query = query.where(
            Task.instructor_id == group.instructor_id,
            Task.is_published == True,
        )
    
    query = query.options(selectinload(Task.instructor))
    query = query.order_by(Task.created_at.desc())
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # 添加统计信息
    response_list = []
    for task in tasks:
        # 统计提交状态
        stats_result = await db.execute(
            select(
                func.count().label("total"),
                func.sum(func.cast(Submission.status == SubmissionStatus.PENDING, Integer)).label("pending"),
                func.sum(func.cast(Submission.status == SubmissionStatus.APPROVED, Integer)).label("approved"),
                func.sum(func.cast(Submission.status == SubmissionStatus.REJECTED, Integer)).label("rejected"),
            ).where(Submission.task_id == task.id)
        )
        stats = stats_result.first()
        
        response = TaskResponse.model_validate(task)
        response.instructor = None  # 简化响应，如需要可保留
        response.submission_count = stats.total or 0
        response.pending_count = int(stats.pending or 0)
        response.approved_count = int(stats.approved or 0)
        response.rejected_count = int(stats.rejected or 0)
        response_list.append(response)
    
    return response_list


@router.post(
    "",
    response_model=TaskResponse,
    summary="创建任务",
)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> TaskResponse:
    """老师创建新的试讲任务/要求。"""
    # 验证批次存在
    semester = await db.get(Semester, task_data.semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="批次不存在")
    
    task = Task(
        title=task_data.title,
        content=task_data.content,
        semester_id=task_data.semester_id,
        instructor_id=current_user.id,
        deadline=task_data.deadline,
        require_lesson_plan=task_data.require_lesson_plan,
        require_video=task_data.require_video,
        is_published=task_data.is_published,
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="获取任务详情",
)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    """获取单个任务的详细信息。"""
    task = await db.get(Task, task_id, options=[selectinload(Task.instructor)])
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 权限检查
    if current_user.role == UserRole.STUDENT:
        if not task.is_published:
            raise HTTPException(status_code=403, detail="任务尚未发布")
        # 验证是否为该学生的导师
        group_result = await db.execute(
            select(Group).where(
                Group.semester_id == task.semester_id,
                Group.instructor_id == task.instructor_id,
                Group.student_id == current_user.id,
            )
        )
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="无权查看此任务")
    elif current_user.role == UserRole.INSTRUCTOR:
        if task.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权查看此任务")
    
    return TaskResponse.model_validate(task)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="更新任务",
)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> TaskResponse:
    """更新任务信息。"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改此任务")
    
    # 更新字段
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.post(
    "/{task_id}/publish",
    response_model=TaskResponse,
    summary="发布任务",
)
async def publish_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> TaskResponse:
    """将任务设为已发布状态。"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此任务")
    
    task.is_published = True
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)


@router.delete(
    "/{task_id}",
    summary="删除任务",
)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> dict:
    """删除任务（仅限未发布的任务）。"""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此任务")
    
    if task.is_published:
        raise HTTPException(status_code=400, detail="已发布的任务不能删除")
    
    await db.delete(task)
    await db.commit()
    
    return {"message": "任务已删除"}
