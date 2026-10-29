"""
Semester management API routes.
Handles lecture practice period/batch management.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, get_current_user
from app.models.user import User
from app.models.semester import Semester, SemesterStatus
from app.models.group import Group
from app.schemas.semester import SemesterCreate, SemesterUpdate, SemesterResponse
from app.schemas.common import PageResult

router = APIRouter()


@router.get(
    "",
    response_model=List[SemesterResponse],
    summary="获取批次列表",
)
async def get_semesters(
    status_filter: Optional[SemesterStatus] = Query(None, description="状态筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> List[SemesterResponse]:
    """获取所有批次列表。"""
    query = select(Semester)
    
    if status_filter:
        query = query.where(Semester.status == status_filter)
    
    query = query.order_by(Semester.created_at.desc())
    result = await db.execute(query)
    semesters = result.scalars().all()
    
    # 添加统计信息
    response_list = []
    for semester in semesters:
        # 统计学生和老师数量
        groups_result = await db.execute(
            select(
                func.count(func.distinct(Group.student_id)),
                func.count(func.distinct(Group.instructor_id)),
            ).where(Group.semester_id == semester.id)
        )
        counts = groups_result.first()
        
        response = SemesterResponse.model_validate(semester)
        response.student_count = counts[0] if counts else 0
        response.instructor_count = counts[1] if counts else 0
        response_list.append(response)
    
    return response_list


@router.post(
    "",
    response_model=SemesterResponse,
    summary="创建批次",
)
async def create_semester(
    semester_data: SemesterCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SemesterResponse:
    """创建新的试讲批次。"""
    # 检查名称是否重复
    existing = await db.execute(
        select(Semester).where(Semester.name == semester_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"批次名称 '{semester_data.name}' 已存在",
        )
    
    semester = Semester(
        name=semester_data.name,
        description=semester_data.description,
        start_date=semester_data.start_date,
        end_date=semester_data.end_date,
        status=SemesterStatus.DRAFT,
    )
    
    db.add(semester)
    await db.commit()
    await db.refresh(semester)
    
    return SemesterResponse.model_validate(semester)


@router.get(
    "/active",
    summary="获取当前进行中的批次",
)
async def get_active_semester(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Optional[SemesterResponse]:
    """获取当前处于进行中状态的批次。如果有多个活跃批次，返回最新的一个。"""
    result = await db.execute(
        select(Semester)
        .where(Semester.status == SemesterStatus.ACTIVE)
        .order_by(Semester.created_at.desc())
        .limit(1)
    )
    semester = result.scalar_one_or_none()
    
    if not semester:
        return None
    
    return SemesterResponse.model_validate(semester)


@router.get(
    "/{semester_id}",
    response_model=SemesterResponse,
    summary="获取批次详情",
)
async def get_semester(
    semester_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SemesterResponse:
    """获取单个批次的详细信息。"""
    semester = await db.get(Semester, semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="批次不存在")
    
    # 统计
    groups_result = await db.execute(
        select(
            func.count(func.distinct(Group.student_id)),
            func.count(func.distinct(Group.instructor_id)),
        ).where(Group.semester_id == semester_id)
    )
    counts = groups_result.first()
    
    response = SemesterResponse.model_validate(semester)
    response.student_count = counts[0] if counts else 0
    response.instructor_count = counts[1] if counts else 0
    
    return response


@router.put(
    "/{semester_id}",
    response_model=SemesterResponse,
    summary="更新批次",
)
async def update_semester(
    semester_id: int,
    semester_data: SemesterUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SemesterResponse:
    """更新批次信息。"""
    semester = await db.get(Semester, semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="批次不存在")
    
    # 检查名称冲突
    if semester_data.name:
        existing = await db.execute(
            select(Semester).where(
                Semester.name == semester_data.name,
                Semester.id != semester_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="批次名称已存在")
    
    # 更新字段
    update_data = semester_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(semester, field, value)
    
    await db.commit()
    await db.refresh(semester)
    
    return SemesterResponse.model_validate(semester)


@router.post(
    "/{semester_id}/start",
    response_model=SemesterResponse,
    summary="开启批次",
)
async def start_semester(
    semester_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SemesterResponse:
    """将批次状态设为进行中。"""
    semester = await db.get(Semester, semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="批次不存在")
    
    if semester.status == SemesterStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="批次已经在进行中")
    
    if semester.status == SemesterStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="已结束的批次不能重新开启")
    
    semester.status = SemesterStatus.ACTIVE
    await db.commit()
    await db.refresh(semester)
    
    return SemesterResponse.model_validate(semester)


@router.post(
    "/{semester_id}/end",
    response_model=SemesterResponse,
    summary="结束批次",
)
async def end_semester(
    semester_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SemesterResponse:
    """将批次状态设为已结束。"""
    semester = await db.get(Semester, semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="批次不存在")
    
    if semester.status == SemesterStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="批次已经结束")
    
    semester.status = SemesterStatus.COMPLETED
    await db.commit()
    await db.refresh(semester)
    
    return SemesterResponse.model_validate(semester)


@router.delete(
    "/{semester_id}",
    summary="删除批次",
)
async def delete_semester(
    semester_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """删除批次（仅限草稿状态）。"""
    semester = await db.get(Semester, semester_id)
    if not semester:
        raise HTTPException(status_code=404, detail="批次不存在")
    
    if semester.status != SemesterStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail="只能删除草稿状态的批次",
        )
    
    await db.delete(semester)
    await db.commit()
    
    return {"message": "批次已删除"}
