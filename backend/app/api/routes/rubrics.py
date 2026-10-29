"""
评分规则(Rubric)管理路由
支持老师创建、编辑、应用评分规则
"""
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.rubric import GradingRubric

router = APIRouter()


# ==================== 请求模型 ====================

class DimensionConfig(BaseModel):
    """维度配置"""
    name: str = Field(..., description="维度名称")
    key: str = Field(..., description="维度标识")
    weight: float = Field(..., ge=0, le=100, description="权重(0-100)")
    description: str = Field("", description="维度描述")


class GradeLevelConfig(BaseModel):
    """评分等级配置"""
    min_score: float = Field(..., ge=0, le=100, description="最低分")
    max_score: float = Field(..., ge=0, le=100, description="最高分")
    label: str = Field(..., description="等级标签")
    description: str = Field("", description="等级描述")


class CreateRubricRequest(BaseModel):
    """创建评分规则请求"""
    name: str = Field(..., description="规则名称")
    description: str = Field("", description="规则描述")
    semester_id: Optional[int] = Field(None, description="批次ID")
    lesson_plan_weight: float = Field(40.0, ge=0, le=100, description="教案权重")
    video_weight: float = Field(60.0, ge=0, le=100, description="视频权重")
    lesson_plan_dimensions: Optional[List[DimensionConfig]] = Field(None, description="教案维度")
    video_dimensions: Optional[List[DimensionConfig]] = Field(None, description="视频维度")
    grade_levels: Optional[List[GradeLevelConfig]] = Field(None, description="评分等级")
    is_default: bool = Field(False, description="是否为默认规则")


class UpdateRubricRequest(BaseModel):
    """更新评分规则请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    lesson_plan_weight: Optional[float] = Field(None, ge=0, le=100)
    video_weight: Optional[float] = Field(None, ge=0, le=100)
    lesson_plan_dimensions: Optional[List[DimensionConfig]] = None
    video_dimensions: Optional[List[DimensionConfig]] = None
    grade_levels: Optional[List[GradeLevelConfig]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


# ==================== 默认配置 ====================

DEFAULT_LESSON_PLAN_DIMENSIONS = [
    {"name": "结构完整性", "key": "structure", "weight": 15, "description": "教案结构是否完整，包含导入、新授、练习、总结等环节"},
    {"name": "教学目标", "key": "objectives", "weight": 15, "description": "三维目标是否明确、可测量"},
    {"name": "重难点分析", "key": "key_points", "weight": 15, "description": "重点突出，难点突破策略合理"},
    {"name": "教学过程", "key": "teaching_process", "weight": 20, "description": "教学环节设计合理，时间分配恰当"},
    {"name": "教学方法", "key": "teaching_methods", "weight": 15, "description": "教学方法多样，符合学情"},
    {"name": "板书设计", "key": "board_design", "weight": 10, "description": "板书清晰有层次"},
    {"name": "教学语言", "key": "language", "weight": 10, "description": "语言规范准确"}
]

DEFAULT_VIDEO_DIMENSIONS = [
    {"name": "语速控制", "key": "speech_rate", "weight": 15, "description": "语速适中(120-160字/分钟)"},
    {"name": "表达流畅度", "key": "fluency", "weight": 20, "description": "表达流畅，减少语气词和停顿"},
    {"name": "手势运用", "key": "gesture", "weight": 15, "description": "手势自然，配合讲解内容"},
    {"name": "姿态仪表", "key": "posture", "weight": 15, "description": "站姿端正，仪表大方"},
    {"name": "眼神交流", "key": "eye_contact", "weight": 20, "description": "目光交流充分，面向学生"},
    {"name": "空间运用", "key": "space_usage", "weight": 15, "description": "合理运用讲台空间"}
]

DEFAULT_GRADE_LEVELS = [
    {"min_score": 90, "max_score": 100, "label": "优秀", "description": "表现出色，全面达标"},
    {"min_score": 80, "max_score": 89, "label": "良好", "description": "表现良好，基本达标"},
    {"min_score": 70, "max_score": 79, "label": "中等", "description": "表现一般，需要改进"},
    {"min_score": 60, "max_score": 69, "label": "及格", "description": "勉强达标，需加强"},
    {"min_score": 0, "max_score": 59, "label": "不及格", "description": "未达标，需重新练习"}
]


# ==================== API 路由 ====================

@router.get("")
async def list_rubrics(
    semester_id: Optional[int] = Query(None, description="批次ID"),
    include_global: bool = Query(True, description="是否包含通用规则"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取评分规则列表
    """
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="学生无权访问")
    
    stmt = select(GradingRubric).where(
        GradingRubric.instructor_id == current_user.id
    )
    
    if semester_id:
        if include_global:
            stmt = stmt.where(
                (GradingRubric.semester_id == semester_id) | 
                (GradingRubric.semester_id.is_(None))
            )
        else:
            stmt = stmt.where(GradingRubric.semester_id == semester_id)
    
    stmt = stmt.order_by(desc(GradingRubric.is_default), desc(GradingRubric.created_at))
    
    result = await db.execute(stmt)
    rubrics = list(result.scalars().all())
    
    return {
        "success": True,
        "data": {
            "items": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "semester_id": r.semester_id,
                    "lesson_plan_weight": r.lesson_plan_weight,
                    "video_weight": r.video_weight,
                    "is_default": r.is_default,
                    "is_active": r.is_active,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in rubrics
            ]
        }
    }


@router.get("/defaults")
async def get_default_dimensions(
    current_user: User = Depends(get_current_user),
):
    """
    获取默认维度配置（用于创建新规则时的参考）
    """
    return {
        "success": True,
        "data": {
            "lesson_plan_dimensions": DEFAULT_LESSON_PLAN_DIMENSIONS,
            "video_dimensions": DEFAULT_VIDEO_DIMENSIONS,
            "grade_levels": DEFAULT_GRADE_LEVELS
        }
    }


@router.post("")
async def create_rubric(
    request: CreateRubricRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建评分规则
    """
    if current_user.role not in [UserRole.INSTRUCTOR, UserRole.ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅老师/管理员可创建")
    
    # 验证权重
    if abs(request.lesson_plan_weight + request.video_weight - 100) > 0.01:
        raise HTTPException(status_code=400, detail="教案权重+视频权重必须等于100")
    
    # 如果设为默认，取消其他默认
    if request.is_default:
        stmt = select(GradingRubric).where(
            and_(
                GradingRubric.instructor_id == current_user.id,
                GradingRubric.is_default == True
            )
        )
        if request.semester_id:
            stmt = stmt.where(GradingRubric.semester_id == request.semester_id)
        
        result = await db.execute(stmt)
        for rubric in result.scalars().all():
            rubric.is_default = False
    
    # 创建规则
    rubric = GradingRubric(
        name=request.name,
        description=request.description,
        instructor_id=current_user.id,
        semester_id=request.semester_id,
        lesson_plan_weight=request.lesson_plan_weight,
        video_weight=request.video_weight,
        lesson_plan_dimensions=json.dumps(
            [d.dict() for d in request.lesson_plan_dimensions] if request.lesson_plan_dimensions 
            else DEFAULT_LESSON_PLAN_DIMENSIONS, 
            ensure_ascii=False
        ),
        video_dimensions=json.dumps(
            [d.dict() for d in request.video_dimensions] if request.video_dimensions 
            else DEFAULT_VIDEO_DIMENSIONS, 
            ensure_ascii=False
        ),
        grade_levels=json.dumps(
            [g.dict() for g in request.grade_levels] if request.grade_levels 
            else DEFAULT_GRADE_LEVELS, 
            ensure_ascii=False
        ),
        is_default=request.is_default,
        is_active=True
    )
    
    db.add(rubric)
    await db.commit()
    await db.refresh(rubric)
    
    return {
        "success": True,
        "data": {"id": rubric.id, "name": rubric.name},
        "message": "评分规则创建成功"
    }


@router.get("/{rubric_id}")
async def get_rubric(
    rubric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取评分规则详情
    """
    rubric = await db.get(GradingRubric, rubric_id)
    
    if not rubric:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    # 权限检查（管理员可查看所有，老师只能查看自己的）
    if current_user.role == UserRole.INSTRUCTOR and rubric.instructor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看")
    
    return {
        "success": True,
        "data": {
            "id": rubric.id,
            "name": rubric.name,
            "description": rubric.description,
            "semester_id": rubric.semester_id,
            "lesson_plan_weight": rubric.lesson_plan_weight,
            "video_weight": rubric.video_weight,
            "lesson_plan_dimensions": json.loads(rubric.lesson_plan_dimensions) if rubric.lesson_plan_dimensions else [],
            "video_dimensions": json.loads(rubric.video_dimensions) if rubric.video_dimensions else [],
            "grade_levels": json.loads(rubric.grade_levels) if rubric.grade_levels else [],
            "is_default": rubric.is_default,
            "is_active": rubric.is_active,
            "created_at": rubric.created_at.isoformat() if rubric.created_at else None,
            "updated_at": rubric.updated_at.isoformat() if rubric.updated_at else None
        }
    }


@router.put("/{rubric_id}")
async def update_rubric(
    rubric_id: int,
    request: UpdateRubricRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新评分规则
    """
    rubric = await db.get(GradingRubric, rubric_id)
    
    if not rubric:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    if rubric.instructor_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="无权修改")
    
    # 验证权重
    lp_weight = request.lesson_plan_weight if request.lesson_plan_weight is not None else rubric.lesson_plan_weight
    video_weight = request.video_weight if request.video_weight is not None else rubric.video_weight
    if abs(lp_weight + video_weight - 100) > 0.01:
        raise HTTPException(status_code=400, detail="教案权重+视频权重必须等于100")
    
    # 更新字段
    if request.name is not None:
        rubric.name = request.name
    if request.description is not None:
        rubric.description = request.description
    if request.lesson_plan_weight is not None:
        rubric.lesson_plan_weight = request.lesson_plan_weight
    if request.video_weight is not None:
        rubric.video_weight = request.video_weight
    if request.lesson_plan_dimensions is not None:
        rubric.lesson_plan_dimensions = json.dumps([d.dict() for d in request.lesson_plan_dimensions], ensure_ascii=False)
    if request.video_dimensions is not None:
        rubric.video_dimensions = json.dumps([d.dict() for d in request.video_dimensions], ensure_ascii=False)
    if request.grade_levels is not None:
        rubric.grade_levels = json.dumps([g.dict() for g in request.grade_levels], ensure_ascii=False)
    if request.is_active is not None:
        rubric.is_active = request.is_active
    
    # 处理默认设置
    if request.is_default is True and not rubric.is_default:
        # 取消其他默认
        stmt = select(GradingRubric).where(
            and_(
                GradingRubric.instructor_id == current_user.id,
                GradingRubric.is_default == True,
                GradingRubric.id != rubric_id
            )
        )
        if rubric.semester_id:
            stmt = stmt.where(GradingRubric.semester_id == rubric.semester_id)
        
        result = await db.execute(stmt)
        for r in result.scalars().all():
            r.is_default = False
        
        rubric.is_default = True
    elif request.is_default is False:
        rubric.is_default = False
    
    await db.commit()
    
    return {
        "success": True,
        "message": "评分规则已更新"
    }


@router.delete("/{rubric_id}")
async def delete_rubric(
    rubric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除评分规则
    """
    rubric = await db.get(GradingRubric, rubric_id)
    
    if not rubric:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    if rubric.instructor_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="无权删除")
    
    await db.delete(rubric)
    await db.commit()
    
    return {
        "success": True,
        "message": "评分规则已删除"
    }


@router.post("/{rubric_id}/apply")
async def apply_rubric_to_grading(
    rubric_id: int,
    submission_id: int = Query(..., description="提交ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    应用评分规则计算建议分数
    
    根据规则的维度权重，结合 AI 分析结果计算综合分数
    """
    from app.models.submission import Submission
    
    rubric = await db.get(GradingRubric, rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    
    # 解析维度配置
    lp_dims = json.loads(rubric.lesson_plan_dimensions) if rubric.lesson_plan_dimensions else []
    video_dims = json.loads(rubric.video_dimensions) if rubric.video_dimensions else []
    
    # 解析分析结果
    lp_analysis = json.loads(submission.lesson_plan_analysis) if submission.lesson_plan_analysis else {}
    video_analysis = json.loads(submission.video_analysis) if submission.video_analysis else {}
    
    # 计算教案得分
    lp_score = 0
    lp_total_weight = 0
    lp_details = []
    
    for dim in lp_dims:
        dim_key = dim["key"]
        dim_weight = dim["weight"]
        
        # 从分析结果中获取该维度得分
        score = 0
        if "dimensions" in lp_analysis and dim_key in lp_analysis["dimensions"]:
            score = lp_analysis["dimensions"][dim_key].get("score", 0)
        
        lp_score += score * dim_weight / 100
        lp_total_weight += dim_weight
        lp_details.append({
            "dimension": dim["name"],
            "key": dim_key,
            "weight": dim_weight,
            "score": score,
            "weighted_score": round(score * dim_weight / 100, 2)
        })
    
    # 归一化教案得分
    if lp_total_weight > 0:
        lp_score = lp_score * 100 / lp_total_weight
    
    # 计算视频得分（简化处理）
    video_score = video_analysis.get("overall_score", 0)
    
    # 计算总分
    total_score = (
        lp_score * rubric.lesson_plan_weight / 100 +
        video_score * rubric.video_weight / 100
    )
    
    # 确定等级
    grade_levels = json.loads(rubric.grade_levels) if rubric.grade_levels else DEFAULT_GRADE_LEVELS
    grade_label = "未评定"
    for level in grade_levels:
        if level["min_score"] <= total_score <= level["max_score"]:
            grade_label = level["label"]
            break
    
    return {
        "success": True,
        "data": {
            "rubric_id": rubric_id,
            "rubric_name": rubric.name,
            "submission_id": submission_id,
            "lesson_plan_score": round(lp_score, 1),
            "video_score": round(video_score, 1),
            "total_score": round(total_score, 1),
            "grade_label": grade_label,
            "weights": {
                "lesson_plan": rubric.lesson_plan_weight,
                "video": rubric.video_weight
            },
            "lesson_plan_details": lp_details
        }
    }
