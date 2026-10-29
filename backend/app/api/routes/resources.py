"""
资源中心路由
提供教学资源的增删改查、AI智能推荐等功能
"""
import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.deps import get_current_user, get_db, require_admin
from app.models.user import User
from app.models.resource import Resource, ResourceCategory
from app.core.config import settings
from app.api.routes.lesson_resources import router as lesson_resources_router
from app.api.routes.audio_resources import router as audio_resources_router
from app.api.routes.lesson_videos import router as lesson_videos_router

logger = logging.getLogger(__name__)

router = APIRouter()

router.include_router(lesson_resources_router)
router.include_router(audio_resources_router)
router.include_router(lesson_videos_router)


# ==================== 请求/响应模型 ====================

class ResourceCreate(BaseModel):
    title: str = Field(..., description="资源标题")
    description: Optional[str] = Field(None, description="资源描述")
    category: str = Field(..., description="资源分类")
    url: Optional[str] = Field(None, description="资源链接")
    cover_image: Optional[str] = Field(None, description="封面图片URL")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    subject: Optional[str] = Field(None, description="学科")
    grade_level: Optional[str] = Field(None, description="适用学段")
    source: Optional[str] = Field(None, description="来源/作者")
    sort_order: Optional[int] = Field(0, description="排序权重")
    is_published: Optional[bool] = Field(True, description="是否发布")
    is_featured: Optional[bool] = Field(False, description="是否精选")
    content: Optional[str] = Field(None, description="详细内容")


class ResourceUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    cover_image: Optional[str] = None
    tags: Optional[List[str]] = None
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    source: Optional[str] = None
    sort_order: Optional[int] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None
    content: Optional[str] = None


class ResourceOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: str
    url: Optional[str] = None
    cover_image: Optional[str] = None
    tags: Optional[List[str]] = None
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    source: Optional[str] = None
    view_count: int = 0
    sort_order: int = 0
    is_published: bool = True
    is_featured: bool = False
    content: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class AIRecommendRequest(BaseModel):
    """AI 智能推荐请求"""
    context: Optional[str] = Field(None, description="学习上下文（如当前练习的学科、主题等）")


# ==================== 辅助函数 ====================

def resource_to_dict(r: Resource) -> dict:
    """将 Resource ORM 对象转为响应字典"""
    tags = None
    if r.tags:
        try:
            tags = json.loads(r.tags)
        except (json.JSONDecodeError, TypeError):
            tags = []
    return {
        "id": r.id,
        "title": r.title,
        "description": r.description,
        "category": r.category.value if r.category else None,
        "url": r.url,
        "cover_image": r.cover_image,
        "tags": tags,
        "subject": r.subject,
        "grade_level": r.grade_level,
        "source": r.source,
        "view_count": r.view_count,
        "sort_order": r.sort_order,
        "is_published": r.is_published,
        "is_featured": r.is_featured,
        "content": r.content,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ==================== 学生端 - 资源列表 ====================

@router.get("/filters")
async def get_resource_filters(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取可用的筛选选项（学科、学段）"""
    subj_result = await db.execute(
        select(Resource.subject).where(
            Resource.is_published == True, Resource.subject.isnot(None)
        ).distinct()
    )
    subjects = sorted([r[0] for r in subj_result.all() if r[0]])

    grade_result = await db.execute(
        select(Resource.grade_level).where(
            Resource.is_published == True, Resource.grade_level.isnot(None)
        ).distinct()
    )
    grade_levels = sorted([r[0] for r in grade_result.all() if r[0]])

    return {"subjects": subjects, "grade_levels": grade_levels}


@router.get("/list")
async def get_resources(
    category: Optional[str] = Query(None, description="分类筛选"),
    subject: Optional[str] = Query(None, description="学科筛选"),
    grade_level: Optional[str] = Query(None, description="学段筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    featured: Optional[bool] = Query(None, description="是否只看精选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取资源列表（学生端）"""
    query = select(Resource).where(Resource.is_published == True)

    if category:
        try:
            cat_enum = ResourceCategory(category)
            query = query.where(Resource.category == cat_enum)
        except ValueError:
            pass

    if subject:
        query = query.where(Resource.subject == subject)

    if grade_level:
        query = query.where(Resource.grade_level == grade_level)

    if featured is True:
        query = query.where(Resource.is_featured == True)

    if keyword:
        kw = f"%{keyword}%"
        query = query.where(
            or_(
                Resource.title.ilike(kw),
                Resource.description.ilike(kw),
                Resource.tags.ilike(kw),
                Resource.subject.ilike(kw),
            )
        )

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页 + 排序
    query = query.order_by(Resource.is_featured.desc(), Resource.sort_order.desc(), Resource.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    resources = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [resource_to_dict(r) for r in resources],
    }


@router.get("/categories")
async def get_resource_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取资源分类及各分类数量"""
    query = (
        select(Resource.category, func.count(Resource.id))
        .where(Resource.is_published == True)
        .group_by(Resource.category)
    )
    result = await db.execute(query)
    rows = result.all()

    category_labels = {
        "video": "教学视频",
        "observation": "观摩课程",
        "website": "资源网站",
        "topic": "优秀选题",
        "document": "教学文档",
    }

    categories = []
    for cat, count in rows:
        cat_value = cat.value if hasattr(cat, 'value') else cat
        categories.append({
            "key": cat_value,
            "label": category_labels.get(cat_value, cat_value),
            "count": count,
        })

    return categories


@router.get("/detail/{resource_id}")
async def get_resource_detail(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取资源详情并增加浏览量"""
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.is_published == True)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    # 增加浏览量
    resource.view_count = (resource.view_count or 0) + 1
    await db.commit()
    await db.refresh(resource)

    return resource_to_dict(resource)


# ==================== AI 智能推荐 ====================

@router.post("/ai-recommend")
async def ai_recommend_resources(
    req: AIRecommendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 根据学生情况智能推荐资源（流式返回）"""
    from app.services.ai_service import get_ai_service

    ai_service = get_ai_service()
    if not ai_service or not ai_service.client:
        raise HTTPException(status_code=503, detail="AI 服务未启用")

    # 获取所有已发布资源的摘要
    result = await db.execute(
        select(Resource)
        .where(Resource.is_published == True)
        .order_by(Resource.is_featured.desc(), Resource.view_count.desc())
        .limit(50)
    )
    resources = result.scalars().all()

    resource_list_text = ""
    for r in resources:
        tags_str = ""
        if r.tags:
            try:
                tags_str = ", ".join(json.loads(r.tags))
            except Exception:
                pass
        cat_label = {
            "video": "教学视频", "observation": "观摩课程",
            "website": "资源网站", "topic": "优秀选题", "document": "教学文档"
        }.get(r.category.value if hasattr(r.category, 'value') else r.category, "其他")

        resource_list_text += (
            f"- [ID:{r.id}] 《{r.title}》 | 分类:{cat_label} | "
            f"学科:{r.subject or '通用'} | 标签:{tags_str or '无'} | "
            f"浏览:{r.view_count}次\n"
        )

    context_info = req.context or "无特定上下文"

    system_prompt = """你是一个师范教育资源推荐AI助手。请根据学生信息和学习上下文，从资源库中推荐最适合的资源，并说明推荐理由。

请按以下格式输出：
1. 先简要分析学生的学习需求
2. 推荐 3-5 个最相关的资源，每个资源说明推荐理由
3. 给出个性化的学习建议

注意：推荐要有针对性，避免泛泛而谈。如果学生有薄弱环节，优先推荐能帮助改进的资源。"""

    user_prompt = f"""## 学生信息
- 姓名: {current_user.name}
- 专业: {current_user.major or '未设置'}
- 班级: {current_user.class_name or '未设置'}

## 学习上下文
{context_info}

## 可推荐的资源库
{resource_list_text}

请根据以上信息为该学生推荐最合适的学习资源。"""

    async def generate():
        try:
            stream = await ai_service.client.chat.completions.create(
                model=ai_service.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
                max_tokens=2048,
                temperature=0.7,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'content': chunk.choices[0].delta.content}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"AI recommend error: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ==================== 管理端 - CRUD ====================

@router.get("/admin/list")
async def admin_get_resources(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员获取所有资源（含未发布）"""
    query = select(Resource)

    if category:
        try:
            cat_enum = ResourceCategory(category)
            query = query.where(Resource.category == cat_enum)
        except ValueError:
            pass

    if keyword:
        kw = f"%{keyword}%"
        query = query.where(
            or_(Resource.title.ilike(kw), Resource.description.ilike(kw))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Resource.sort_order.desc(), Resource.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    resources = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [resource_to_dict(r) for r in resources],
    }


@router.post("/admin/create")
async def admin_create_resource(
    data: ResourceCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员创建资源"""
    resource = Resource(
        title=data.title,
        description=data.description,
        category=ResourceCategory(data.category),
        url=data.url,
        cover_image=data.cover_image,
        tags=json.dumps(data.tags, ensure_ascii=False) if data.tags else None,
        subject=data.subject,
        grade_level=data.grade_level,
        source=data.source,
        sort_order=data.sort_order or 0,
        is_published=data.is_published if data.is_published is not None else True,
        is_featured=data.is_featured or False,
        content=data.content,
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource_to_dict(resource)


@router.put("/admin/update/{resource_id}")
async def admin_update_resource(
    resource_id: int,
    data: ResourceUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员更新资源"""
    result = await db.execute(select(Resource).where(Resource.id == resource_id))
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"], ensure_ascii=False)
    if "category" in update_data and update_data["category"] is not None:
        update_data["category"] = ResourceCategory(update_data["category"])

    for key, value in update_data.items():
        setattr(resource, key, value)

    await db.commit()
    await db.refresh(resource)
    return resource_to_dict(resource)


@router.delete("/admin/delete/{resource_id}")
async def admin_delete_resource(
    resource_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员删除资源"""
    result = await db.execute(select(Resource).where(Resource.id == resource_id))
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    await db.delete(resource)
    await db.commit()
    return {"message": "删除成功"}
