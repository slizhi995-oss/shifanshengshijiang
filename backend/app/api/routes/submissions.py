"""
Submission API routes.
Handles student file uploads and instructor grading.
"""
import os
import uuid
import aiofiles
from datetime import datetime
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_student, require_instructor
from app.models.user import User, UserRole
from app.models.task import Task
from app.models.group import Group
from app.models.submission import Submission, SubmissionStatus
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionResponse,
    SubmissionReview,
    SubmissionReject,
    SubmissionStatusOverview,
)
from app.schemas.common import PageParams, PageResult

router = APIRouter()


async def save_upload_file(
    file: UploadFile,
    subfolder: str,
) -> Tuple[str, str]:
    """
    异步保存上传的文件。
    
    Args:
        file: 上传的文件对象
        subfolder: 子目录名 (如 'lesson_plans' 或 'videos')
    
    Returns:
        (file_path, original_filename) 元组
    """
    # 创建上传目录
    upload_dir = os.path.join(settings.UPLOAD_DIR, subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 生成唯一文件名
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # 异步写入文件
    async with aiofiles.open(file_path, "wb") as out_file:
        # 分块读写，适合大文件
        while content := await file.read(1024 * 1024):  # 1MB chunks
            await out_file.write(content)
    
    # 返回相对路径和原始文件名
    relative_path = os.path.join(subfolder, unique_filename)
    return relative_path, file.filename or unique_filename


def validate_file_type(file: UploadFile, allowed_types: List[str]) -> None:
    """验证文件类型。"""
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}",
        )


@router.post(
    "/upload",
    response_model=SubmissionResponse,
    summary="学生提交作业",
)
async def submit_assignment(
    task_id: int = Form(..., description="任务ID"),
    student_remark: Optional[str] = Form(None, description="学生备注"),
    lesson_plan: Optional[UploadFile] = File(None, description="教案PDF"),
    video: Optional[UploadFile] = File(None, description="讲课视频"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student),
) -> SubmissionResponse:
    """
    学生提交作业（教案和/或视频）。
    
    支持大文件上传，使用异步分块写入。
    
    验证：
    - 学生必须是任务发布老师的学生
    - 文件类型必须符合要求
    """
    # 验证任务存在
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if not task.is_published:
        raise HTTPException(status_code=400, detail="任务尚未发布")
    
    # 验证学生是否属于该老师
    group_result = await db.execute(
        select(Group).where(
            Group.semester_id == task.semester_id,
            Group.instructor_id == task.instructor_id,
            Group.student_id == current_user.id,
        )
    )
    if not group_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="您不是该任务的目标学生")
    
    # 验证文件要求
    if task.require_lesson_plan and not lesson_plan:
        raise HTTPException(status_code=400, detail="请上传教案文件")
    if task.require_video and not video:
        raise HTTPException(status_code=400, detail="请上传讲课视频")
    
    # 验证文件类型
    if lesson_plan:
        validate_file_type(lesson_plan, settings.ALLOWED_DOCUMENT_TYPES)
    if video:
        validate_file_type(video, settings.ALLOWED_VIDEO_TYPES)
    
    # 查找或创建提交记录
    submission_result = await db.execute(
        select(Submission).where(
            Submission.task_id == task_id,
            Submission.student_id == current_user.id,
        )
    )
    submission = submission_result.scalar_one_or_none()
    
    if submission:
        # 已存在提交，检查状态
        if submission.status == SubmissionStatus.APPROVED:
            raise HTTPException(status_code=400, detail="作业已通过审核，无法重新提交")
        # 更新提交次数
        submission.submit_count += 1
    else:
        submission = Submission(
            task_id=task_id,
            student_id=current_user.id,
            submit_count=1,
        )
        db.add(submission)
    
    # 保存文件
    if lesson_plan:
        path, name = await save_upload_file(lesson_plan, "lesson_plans")
        submission.lesson_plan_path = path
        submission.lesson_plan_name = name
    
    if video:
        path, name = await save_upload_file(video, "videos")
        submission.video_path = path
        submission.video_name = name
    
    # 更新提交信息
    submission.student_remark = student_remark
    submission.status = SubmissionStatus.PENDING
    submission.submitted_at = datetime.now()
    submission.reject_reason = None  # 清除之前的驳回原因
    
    await db.commit()
    await db.refresh(submission)

    # 显式构造响应对象，避免在 Pydantic 校验阶段访问 ORM 懒加载属性触发 MissingGreenlet
    return SubmissionResponse(
        id=submission.id,
        task_id=submission.task_id,
        task_title=task.title,
        student_id=submission.student_id,
        lesson_plan_path=submission.lesson_plan_path,
        lesson_plan_name=submission.lesson_plan_name,
        video_path=submission.video_path,
        video_name=submission.video_name,
        student_remark=submission.student_remark,
        status=submission.status,
        lesson_plan_score=submission.lesson_plan_score,
        video_score=submission.video_score,
        total_score=submission.total_score,
        feedback=submission.feedback,
        reject_reason=submission.reject_reason,
        submitted_at=submission.submitted_at,
        reviewed_at=submission.reviewed_at,
        submit_count=submission.submit_count,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
        student=None,
        task=None,
    )


@router.get(
    "/my",
    response_model=List[SubmissionResponse],
    summary="获取我的提交记录",
)
async def get_my_submissions(
    semester_id: Optional[int] = Query(None, description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student),
) -> List[SubmissionResponse]:
    """获取当前学生的所有提交记录。"""
    query = (
        select(Submission)
        .where(Submission.student_id == current_user.id)
        .options(selectinload(Submission.task))
        .order_by(Submission.created_at.desc())
    )
    
    if semester_id:
        query = query.join(Task).where(Task.semester_id == semester_id)
    
    result = await db.execute(query)
    submissions = result.scalars().all()
    
    # 显式构造响应列表，避免在 Pydantic 校验阶段访问 ORM 懒加载属性触发 MissingGreenlet
    responses: List[SubmissionResponse] = []
    for s in submissions:
      responses.append(
        SubmissionResponse(
            id=s.id,
            task_id=s.task_id,
            task_title=s.task.title if s.task else None,
            student_id=s.student_id,
            lesson_plan_path=s.lesson_plan_path,
            lesson_plan_name=s.lesson_plan_name,
            video_path=s.video_path,
            video_name=s.video_name,
            student_remark=s.student_remark,
            status=s.status,
            lesson_plan_score=s.lesson_plan_score,
            video_score=s.video_score,
            total_score=s.total_score,
            feedback=s.feedback,
            reject_reason=s.reject_reason,
            submitted_at=s.submitted_at,
            reviewed_at=s.reviewed_at,
            submit_count=s.submit_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
            student=None,
            task=None,
        )
      )
    
    return responses


@router.get(
    "/my/status",
    response_model=SubmissionStatusOverview,
    summary="获取我的提交状态概览",
)
async def get_my_submission_status(
    semester_id: int = Query(..., description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_student),
) -> SubmissionStatusOverview:
    """获取当前学生在指定批次的提交状态统计。"""
    # 获取该批次中分配给学生的老师发布的任务
    group_result = await db.execute(
        select(Group).where(
            Group.semester_id == semester_id,
            Group.student_id == current_user.id,
        )
    )
    group = group_result.scalar_one_or_none()
    
    if not group:
        return SubmissionStatusOverview(
            total_tasks=0,
            submitted=0,
            pending=0,
            approved=0,
            rejected=0,
            not_submitted=0,
        )
    
    # 获取老师发布的已发布任务
    tasks_result = await db.execute(
        select(Task).where(
            Task.semester_id == semester_id,
            Task.instructor_id == group.instructor_id,
            Task.is_published == True,
        )
    )
    tasks = tasks_result.scalars().all()
    total_tasks = len(tasks)
    task_ids = [t.id for t in tasks]
    
    if not task_ids:
        return SubmissionStatusOverview(
            total_tasks=0,
            submitted=0,
            pending=0,
            approved=0,
            rejected=0,
            not_submitted=0,
        )
    
    # 统计提交状态
    submissions_result = await db.execute(
        select(Submission).where(
            Submission.task_id.in_(task_ids),
            Submission.student_id == current_user.id,
        )
    )
    submissions = submissions_result.scalars().all()
    
    submitted = len(submissions)
    pending = sum(1 for s in submissions if s.status == SubmissionStatus.PENDING)
    approved = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
    rejected = sum(1 for s in submissions if s.status == SubmissionStatus.REJECTED)
    
    return SubmissionStatusOverview(
        total_tasks=total_tasks,
        submitted=submitted,
        pending=pending,
        approved=approved,
        rejected=rejected,
        not_submitted=total_tasks - submitted,
    )


@router.get(
    "/instructor",
    response_model=PageResult[SubmissionResponse],
    summary="获取待批改的提交",
)
async def get_submissions_for_review(
    semester_id: int = Query(..., description="批次ID"),
    student_id: Optional[int] = Query(None, description="学生ID筛选"),
    status_filter: Optional[SubmissionStatus] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> PageResult[SubmissionResponse]:
    """
    获取当前老师需要批改的学生提交。
    
    可按状态筛选。
    """
    # 构建查询
    query = (
        select(Submission)
        .join(Task)
        .where(
            Task.semester_id == semester_id,
            Task.instructor_id == current_user.id,
        )
        .options(
            selectinload(Submission.student),
            selectinload(Submission.task).selectinload(Task.instructor),
        )
    )

    if student_id:
        query = query.where(Submission.student_id == student_id)
    
    if status_filter:
        query = query.where(Submission.status == status_filter)
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # 分页
    query = query.order_by(Submission.submitted_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    submissions = result.scalars().all()
    
    return PageResult.create(
        items=[SubmissionResponse.model_validate(s) for s in submissions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{submission_id}/grade",
    response_model=SubmissionResponse,
    summary="保存评分（不改变通过状态）",
)
async def grade_submission(
    submission_id: int,
    review: SubmissionReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> SubmissionResponse:
    """
    老师保存评分，状态变为"已评分"。
    
    打分和通过/驳回是分开的操作，可以先打分后再决定通过或驳回。
    """
    submission = await db.get(
        Submission,
        submission_id,
        options=[
            selectinload(Submission.task),
            selectinload(Submission.student)
        ],
    )
    
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    # 验证是否为该老师的学生提交
    if submission.task.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此提交")
    
    # 更新评分，状态变为已评分（如果还未通过）
    submission.lesson_plan_score = review.lesson_plan_score
    submission.video_score = review.video_score
    submission.total_score = review.total_score
    submission.feedback = review.feedback
    
    # 只有待批改状态才改为已评分，已通过的保持不变
    if submission.status in (SubmissionStatus.PENDING, SubmissionStatus.REJECTED):
        submission.status = SubmissionStatus.GRADED
    
    submission.reviewed_at = datetime.now()
    
    # 记录触发画像需要的信息
    _student_id = submission.student_id
    _task_id = submission.task_id

    await db.commit()
    db.expire_all()
    
    # 重新查询带关系的对象
    result = await db.execute(
        select(Submission)
        .options(
            selectinload(Submission.task).selectinload(Task.instructor),
            selectinload(Submission.student)
        )
        .where(Submission.id == submission_id)
    )
    submission = result.scalar_one()
    
    # 使用独立会话触发画像更新
    try:
        from app.services.profile_service import profile_service
        from app.core.database import async_session_factory
        async with async_session_factory() as profile_db:
            task_obj = await profile_db.get(Task, _task_id)
            if task_obj:
                await profile_service.compute_student_profile(
                    profile_db, _student_id, task_obj.semester_id
                )
    except Exception as e:
        import logging
        logging.warning(f"评分后画像更新失败: {e}")

    return SubmissionResponse.model_validate(submission)


@router.post(
    "/{submission_id}/approve",
    response_model=SubmissionResponse,
    summary="审核通过",
)
async def approve_submission(
    submission_id: int,
    review: Optional[SubmissionReview] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> SubmissionResponse:
    """
    老师审核通过学生提交。
    
    可以同时传入评分，也可以使用已保存的评分直接通过。
    """
    submission = await db.get(
        Submission,
        submission_id,
        options=[
            selectinload(Submission.task),
            selectinload(Submission.student)
        ],
    )
    
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    # 验证是否为该老师的学生提交
    if submission.task.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此提交")
    
    # 如果传入了评分，更新评分
    if review:
        submission.lesson_plan_score = review.lesson_plan_score
        submission.video_score = review.video_score
        submission.total_score = review.total_score
        submission.feedback = review.feedback
    else:
        # 没有传入评分，检查是否已有评分
        if submission.total_score is None:
            raise HTTPException(status_code=400, detail="请先评分后再通过")
    
    submission.status = SubmissionStatus.APPROVED
    submission.reviewed_at = datetime.now()
    submission.reject_reason = None
    
    # 记录触发画像需要的信息
    _student_id = submission.student_id
    _task_id = submission.task_id

    await db.commit()
    db.expire_all()  # 清除缓存
    
    # 重新查询带关系的对象
    result = await db.execute(
        select(Submission)
        .options(
            selectinload(Submission.task).selectinload(Task.instructor),
            selectinload(Submission.student)
        )
        .where(Submission.id == submission_id)
    )
    submission = result.scalar_one()
    
    # 使用独立会话触发画像更新（避免 greenlet 错误）
    try:
        from app.services.profile_service import profile_service
        from app.core.database import async_session_factory
        async with async_session_factory() as profile_db:
            task_obj = await profile_db.get(Task, _task_id)
            if task_obj:
                await profile_service.compute_student_profile(
                    profile_db, _student_id, task_obj.semester_id
                )
    except Exception as e:
        import logging
        logging.warning(f"审核通过后画像更新失败: {e}")
    
    return SubmissionResponse.model_validate(submission)


@router.post(
    "/{submission_id}/reject",
    response_model=SubmissionResponse,
    summary="驳回提交",
)
async def reject_submission(
    submission_id: int,
    reject_data: SubmissionReject,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> SubmissionResponse:
    """
    老师驳回学生提交，学生需重新上传。
    
    必须填写驳回原因。
    """
    submission = await db.get(
        Submission,
        submission_id,
        options=[
            selectinload(Submission.task),
            selectinload(Submission.student)
        ],
    )
    
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    if submission.task.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此提交")
    
    # 更新状态
    submission.status = SubmissionStatus.REJECTED
    submission.reject_reason = reject_data.reject_reason
    submission.reviewed_at = datetime.now()
    # 清除之前的评分
    submission.lesson_plan_score = None
    submission.video_score = None
    submission.total_score = None
    
    await db.commit()
    db.expire_all()  # 清除缓存
    
    # 重新查询带关系的对象
    result = await db.execute(
        select(Submission)
        .options(
            selectinload(Submission.task).selectinload(Task.instructor),
            selectinload(Submission.student)
        )
        .where(Submission.id == submission_id)
    )
    submission = result.scalar_one()
    
    return SubmissionResponse.model_validate(submission)


@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse,
    summary="获取提交详情",
)
async def get_submission_detail(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmissionResponse:
    """获取提交的详细信息。"""
    submission = await db.get(
        Submission,
        submission_id,
        options=[
            selectinload(Submission.student),
            selectinload(Submission.task).selectinload(Task.instructor),
        ],
    )
    
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    # 权限检查：学生只能看自己的，老师可查看所有提交（便于跨组协作）
    if current_user.role == UserRole.STUDENT:
        if submission.student_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权查看")
    
    return SubmissionResponse.model_validate(submission)


# ==================== AI 辅助批改接口 ====================

@router.post(
    "/{submission_id}/ai-grade",
    summary="AI 综合批改（生成建议分数和评语）",
)
async def ai_comprehensive_grading(
    submission_id: int,
    lesson_plan_weight: float = Query(0.4, ge=0, le=1, description="教案权重"),
    video_weight: float = Query(0.6, ge=0, le=1, description="视频权重"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
):
    """
    AI 综合批改
    
    结合教案分析和视频分析，生成：
    - 建议分数（教案分、视频分、综合分）
    - 综合评语
    - 亮点摘要
    - 改进建议
    
    老师可根据 AI 建议调整最终分数
    """
    from app.services.grading_service import comprehensive_grading_service
    
    submission = await db.get(
        Submission,
        submission_id,
        options=[selectinload(Submission.task)],
    )
    
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    if submission.task.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此提交")
    
    # 验证权重
    if abs(lesson_plan_weight + video_weight - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail="权重之和必须等于1")
    
    try:
        result = await comprehensive_grading_service.generate_comprehensive_feedback(
            db,
            submission_id,
            custom_weights={
                "lesson_plan": lesson_plan_weight,
                "video": video_weight
            }
        )
        
        return {
            "success": True,
            "data": result,
            "message": "AI 批改完成，请查看建议分数和评语"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 批改失败: {str(e)}")


@router.get(
    "/{submission_id}/analysis",
    summary="获取 AI 分析结果",
)
async def get_submission_analysis(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取提交的 AI 分析结果（教案+视频）
    """
    import json
    
    submission = await db.get(
        Submission,
        submission_id,
        options=[selectinload(Submission.task)],
    )
    
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    # 权限检查
    if current_user.role == UserRole.STUDENT:
        if submission.student_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权查看")
    elif current_user.role == UserRole.INSTRUCTOR:
        if submission.task.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权查看")
    
    lesson_plan_analysis = None
    video_analysis = None
    
    if submission.lesson_plan_analysis:
        try:
            lesson_plan_analysis = json.loads(submission.lesson_plan_analysis)
        except:
            pass
    
    if submission.video_analysis:
        try:
            video_analysis = json.loads(submission.video_analysis)
        except:
            pass
    
    return {
        "success": True,
        "data": {
            "submission_id": submission_id,
            "lesson_plan_analysis": lesson_plan_analysis,
            "video_analysis": video_analysis,
            "ai_suggested_score": submission.ai_suggested_score,
            "ai_suggested_feedback": submission.ai_suggested_feedback,
            "has_lesson_plan": submission.lesson_plan_path is not None,
            "has_video": submission.video_path is not None
        }
    }

