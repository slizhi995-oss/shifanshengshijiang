"""
AI 模型配置管理路由
管理员可以添加、编辑、删除 AI 模型配置
用户可以查看可用的模型列表并选择使用
"""
from typing import Optional, List, Literal
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, or_
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.ai_config import AIModelConfig, AIModelUsageLog
from app.services.model_api import check_model_connection

router = APIRouter()


# ==================== 请求/响应模型 ====================

class AIModelConfigCreate(BaseModel):
    """创建 AI 模型配置"""
    name: str = Field(..., min_length=1, max_length=64, description="模型显示名称")
    provider: str = Field(..., min_length=1, max_length=32, description="模型提供商")
    model_id: str = Field(..., min_length=1, max_length=64, description="模型API标识符")
    api_key: str = Field(..., min_length=1, description="API密钥")
    api_base_url: Optional[str] = Field(None, description="API基础URL")
    model_type: Literal["text", "audio", "vision"] = Field("text", description="模型类型: text/audio/vision")
    is_enabled: bool = Field(True, description="是否启用")
    is_default: bool = Field(False, description="是否为默认模型")
    priority: int = Field(100, description="排序优先级")
    max_tokens: int = Field(4096, description="单次调用最大Token数")
    temperature: float = Field(0.7, ge=0, le=2, description="温度参数")
    price_per_1k_tokens: float = Field(0.002, ge=0, description="每千Token价格(元)")
    description: Optional[str] = Field(None, description="模型描述")
    remark: Optional[str] = Field(None, description="备注信息")
    monthly_quota: Optional[int] = Field(None, ge=0, description="月度Token额度，None表示不限")


class AIModelConfigUpdate(BaseModel):
    """更新 AI 模型配置"""
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    provider: Optional[str] = Field(None, min_length=1, max_length=32)
    model_id: Optional[str] = Field(None, min_length=1, max_length=64)
    api_key: Optional[str] = Field(None, min_length=1)
    api_base_url: Optional[str] = None
    model_type: Optional[Literal["text", "audio", "vision"]] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    priority: Optional[int] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)
    price_per_1k_tokens: Optional[float] = Field(None, ge=0)
    description: Optional[str] = None
    remark: Optional[str] = None
    monthly_quota: Optional[int] = Field(None, ge=0)


class AIModelConfigResponse(BaseModel):
    """AI 模型配置响应"""
    id: int
    name: str
    provider: str
    model_id: str
    api_base_url: Optional[str]
    model_type: str
    is_enabled: bool
    is_default: bool
    priority: int
    max_tokens: int
    temperature: float
    price_per_1k_tokens: float
    description: Optional[str]
    remark: Optional[str]
    monthly_quota: Optional[int] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    # 不返回 api_key，仅管理员可以编辑时看到部分
    api_key_masked: Optional[str] = None
    
    class Config:
        from_attributes = True


# ==================== 管理员接口 ====================

@router.get("/models", summary="获取所有模型配置")
async def list_ai_models(
    model_type: Optional[str] = Query(None, description="按类型筛选"),
    include_disabled: bool = Query(False, description="是否包含禁用的模型"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取 AI 模型配置列表
    
    - 管理员：可以看到所有模型（包括禁用的），可以看到 API Key（部分掩码）
    - 普通用户：只能看到启用的模型，不能看到 API Key
    """
    is_admin = current_user.role in [UserRole.ADMIN]
    
    stmt = select(AIModelConfig)
    
    # 非管理员只能看启用的
    if not is_admin or not include_disabled:
        stmt = stmt.where(AIModelConfig.is_enabled == True)
    
    # 按类型筛选
    if model_type:
        stmt = stmt.where(AIModelConfig.model_type == model_type)
    
    stmt = stmt.order_by(AIModelConfig.priority, AIModelConfig.created_at)
    
    result = await db.execute(stmt)
    models = list(result.scalars().all())
    
    # 构建响应
    items = []
    for model in models:
        item = {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "model_id": model.model_id,
            "api_base_url": model.api_base_url,
            "model_type": model.model_type,
            "is_enabled": model.is_enabled,
            "is_default": model.is_default,
            "priority": model.priority,
            "max_tokens": model.max_tokens,
            "temperature": model.temperature,
            "price_per_1k_tokens": model.price_per_1k_tokens,
            "description": model.description,
            "remark": model.remark,
            "monthly_quota": model.monthly_quota,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }
        
        # 管理员可以看到部分掩码的 API Key
        if is_admin:
            key = model.api_key
            if len(key) > 8:
                item["api_key_masked"] = key[:4] + "*" * (len(key) - 8) + key[-4:]
            else:
                item["api_key_masked"] = "*" * len(key)
        
        items.append(item)
    
    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(items)
        }
    }


@router.post("/models", summary="添加模型配置")
async def create_ai_model(
    config: AIModelConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    添加新的 AI 模型配置（仅管理员）
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    # 如果设置为默认，先取消其他同类型的默认
    if config.is_default:
        stmt = select(AIModelConfig).where(
            and_(
                AIModelConfig.model_type == config.model_type,
                AIModelConfig.is_default == True
            )
        )
        result = await db.execute(stmt)
        for existing in result.scalars().all():
            existing.is_default = False
    
    # 创建新配置
    new_model = AIModelConfig(
        name=config.name,
        provider=config.provider,
        model_id=config.model_id,
        api_key=config.api_key,
        api_base_url=config.api_base_url,
        model_type=config.model_type,
        is_enabled=config.is_enabled,
        is_default=config.is_default,
        priority=config.priority,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        price_per_1k_tokens=config.price_per_1k_tokens,
        description=config.description,
        remark=config.remark,
        monthly_quota=config.monthly_quota,
    )
    
    db.add(new_model)
    await db.commit()
    await db.refresh(new_model)
    
    return {
        "success": True,
        "message": "模型配置添加成功",
        "data": {
            "id": new_model.id,
            "name": new_model.name
        }
    }


@router.get("/models/{model_id}", summary="获取模型详情")
async def get_ai_model(
    model_id: int = Path(..., description="模型配置ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取单个模型配置详情（仅管理员可看完整 API Key）
    """
    model = await db.get(AIModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    
    is_admin = current_user.role in [UserRole.ADMIN]
    
    response = {
        "id": model.id,
        "name": model.name,
        "provider": model.provider,
        "model_id": model.model_id,
        "api_base_url": model.api_base_url,
        "model_type": model.model_type,
        "is_enabled": model.is_enabled,
        "is_default": model.is_default,
        "priority": model.priority,
        "max_tokens": model.max_tokens,
        "temperature": model.temperature,
        "price_per_1k_tokens": model.price_per_1k_tokens,
        "description": model.description,
        "remark": model.remark,
        "monthly_quota": model.monthly_quota,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }
    
    # 管理员可以看到完整 API Key
    if is_admin:
        response["api_key"] = model.api_key
    
    return {
        "success": True,
        "data": response
    }


@router.put("/models/{model_id}", summary="更新模型配置")
async def update_ai_model(
    model_id: int = Path(..., description="模型配置ID"),
    config: AIModelConfigUpdate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新 AI 模型配置（仅管理员）
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    model = await db.get(AIModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    
    # 如果设置为默认，先取消其他同类型的默认
    if config.is_default:
        model_type = config.model_type or model.model_type
        stmt = select(AIModelConfig).where(
            and_(
                AIModelConfig.model_type == model_type,
                AIModelConfig.is_default == True,
                AIModelConfig.id != model_id
            )
        )
        result = await db.execute(stmt)
        for existing in result.scalars().all():
            existing.is_default = False
    
    # 更新字段
    update_data = config.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model, key, value)
    
    await db.commit()
    
    return {
        "success": True,
        "message": "模型配置更新成功"
    }


@router.delete("/models/{model_id}", summary="删除模型配置")
async def delete_ai_model(
    model_id: int = Path(..., description="模型配置ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除 AI 模型配置（仅管理员）
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    model = await db.get(AIModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    
    await db.delete(model)
    await db.commit()
    
    return {
        "success": True,
        "message": "模型配置删除成功"
    }


@router.post("/models/{model_id}/set-default", summary="设置为默认模型")
async def set_default_model(
    model_id: int = Path(..., description="模型配置ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    设置某个模型为该类型的默认模型（仅管理员）
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    model = await db.get(AIModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    
    if not model.is_enabled:
        raise HTTPException(status_code=400, detail="禁用的模型不能设为默认")
    
    # 取消同类型其他模型的默认状态
    stmt = select(AIModelConfig).where(
        and_(
            AIModelConfig.model_type == model.model_type,
            AIModelConfig.is_default == True,
            AIModelConfig.id != model_id
        )
    )
    result = await db.execute(stmt)
    for existing in result.scalars().all():
        existing.is_default = False
    
    # 设置当前模型为默认
    model.is_default = True
    await db.commit()
    
    return {
        "success": True,
        "message": f"已将 {model.name} 设为默认{model.model_type}模型"
    }


@router.post("/models/{model_id}/toggle", summary="启用/禁用模型")
async def toggle_model(
    model_id: int = Path(..., description="模型配置ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    切换模型的启用/禁用状态（仅管理员）
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    model = await db.get(AIModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    
    # 如果是默认模型且要禁用，需要先取消默认
    if model.is_default and model.is_enabled:
        model.is_default = False
    
    model.is_enabled = not model.is_enabled
    await db.commit()
    
    status = "启用" if model.is_enabled else "禁用"
    return {
        "success": True,
        "message": f"已{status}模型 {model.name}",
        "data": {
            "is_enabled": model.is_enabled
        }
    }


@router.post("/models/test-connection", summary="测试模型连接")
async def test_model_connection(
    config: AIModelConfigCreate,
    current_user: User = Depends(get_current_user),
):
    """
    测试 AI 模型 API 连接（仅管理员）
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    try:
        await check_model_connection(config.model_dump())
        return {
            "success": True,
            "message": "连接测试成功",
            "data": {"response_code": 200, "model_type": config.model_type},
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"连接测试失败: {str(e)}"
        }


# ==================== 余额查询 ====================

@router.get("/models/{model_id}/balance", summary="查询模型 API 账户余额")
async def check_model_balance(
    model_id: int = Path(..., description="模型配置ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查询指定模型的 API 账户余额（仅管理员）
    支持：DashScope / DeepSeek / OpenAI(usage)
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    model = await db.get(AIModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")

    import httpx

    provider = model.provider.lower()
    api_key = model.api_key
    result: dict = {"provider": provider, "supported": True, "balance": None, "currency": "CNY", "message": ""}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider in ("dashscope", "aliyun", "qwen"):
                # 阿里云 DashScope 余额查询
                resp = await client.get(
                    "https://dashscope.aliyuncs.com/api/v1/billing/balance",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    balance_info = data.get("data", {})
                    result["balance"] = float(balance_info.get("currency_balance", 0))
                    result["currency"] = "CNY"
                    result["message"] = "查询成功"
                else:
                    result["message"] = f"查询失败 (HTTP {resp.status_code}): {resp.text[:200]}"

            elif provider == "deepseek":
                resp = await client.get(
                    "https://api.deepseek.com/user/balance",
                    headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    info = data.get("balance_infos", [{}])[0] if data.get("balance_infos") else {}
                    result["balance"] = float(info.get("total_balance", 0))
                    result["currency"] = info.get("currency", "CNY")
                    result["granted_balance"] = float(info.get("granted_balance", 0))
                    result["topped_up_balance"] = float(info.get("topped_up_balance", 0))
                    result["message"] = "查询成功"
                else:
                    result["message"] = f"查询失败 (HTTP {resp.status_code})"

            elif provider == "openai":
                # OpenAI 没有直接余额 API，返回使用量估算
                result["supported"] = False
                result["message"] = "OpenAI 不提供余额查询 API，请在 platform.openai.com 查看"

            elif provider == "zhipu":
                result["supported"] = False
                result["message"] = "智谱 AI 请在控制台查看余额"

            elif provider == "moonshot":
                resp = await client.get(
                    "https://api.moonshot.cn/v1/users/me/balance",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result["balance"] = float(data.get("data", {}).get("available_balance", 0))
                    result["currency"] = "CNY"
                    result["message"] = "查询成功"
                else:
                    result["message"] = f"查询失败 (HTTP {resp.status_code})"

            else:
                result["supported"] = False
                result["message"] = f"暂不支持 {provider} 的余额查询"

    except Exception as e:
        result["message"] = f"查询出错: {str(e)}"

    # 同时返回本系统内的消耗统计
    from sqlalchemy import func as sqlfunc
    from app.models.rubric import AICallLog
    consumption_row = await db.execute(
        select(
            sqlfunc.sum(AICallLog.input_tokens + AICallLog.output_tokens).label("tokens"),
            sqlfunc.count(AICallLog.id).label("calls"),
        ).where(AICallLog.model == model.model_id)
    )
    c = consumption_row.one()
    result["local_stats"] = {
        "total_tokens": int(c.tokens or 0),
        "total_calls": int(c.calls or 0),
        "estimated_cost": round(int(c.tokens or 0) / 1000 * model.price_per_1k_tokens, 4),
    }

    return {"success": True, "data": result}


# ==================== 用户接口 ====================

@router.get("/available-models", summary="获取可用模型列表")
async def get_available_models(
    model_type: Optional[str] = Query(None, description="模型类型筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户可用的模型列表（用于用户选择模型）
    
    - 只返回启用的模型
    - 不返回 API Key
    - 标记默认模型
    """
    stmt = select(AIModelConfig).where(AIModelConfig.is_enabled == True)
    
    if model_type:
        stmt = stmt.where(AIModelConfig.model_type == model_type)
    
    stmt = stmt.order_by(AIModelConfig.priority, AIModelConfig.created_at)
    
    result = await db.execute(stmt)
    models = list(result.scalars().all())
    
    items = [
        {
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "model_type": model.model_type,
            "is_default": model.is_default,
            "description": model.description,
        }
        for model in models
    ]
    
    return {
        "success": True,
        "data": {
            "items": items,
            "total": len(items)
        }
    }


# ==================== 调用日志 ====================

@router.get("/usage-logs", summary="获取详细调用日志")
async def list_usage_logs(
    model_id: Optional[int] = Query(None, description="按模型ID筛选"),
    usage_type: Optional[str] = Query(None, description="按调用类型筛选"),
    is_success: Optional[bool] = Query(None, description="按成功/失败筛选"),
    range: str = Query("week", description="时间范围: day/week/month/all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取逐条 AI 调用日志，支持分页和多维筛选（仅管理员）
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可查看")

    now = datetime.utcnow()
    if range == "day":
        start_date = now - timedelta(days=1)
    elif range == "week":
        start_date = now - timedelta(days=7)
    elif range == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = None

    conditions = []
    if start_date:
        conditions.append(AIModelUsageLog.created_at >= start_date)
    if model_id is not None:
        conditions.append(AIModelUsageLog.model_config_id == model_id)
    if usage_type:
        conditions.append(AIModelUsageLog.usage_type == usage_type)
    if is_success is not None:
        conditions.append(AIModelUsageLog.is_success == is_success)

    base_stmt = select(AIModelUsageLog)
    if conditions:
        base_stmt = base_stmt.where(and_(*conditions))

    # 总数
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页
    stmt = base_stmt.order_by(desc(AIModelUsageLog.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    logs = list(result.scalars().all())

    # 批量查模型名
    model_ids = list({log.model_config_id for log in logs})
    model_map: dict = {}
    if model_ids:
        m_result = await db.execute(select(AIModelConfig).where(AIModelConfig.id.in_(model_ids)))
        for m in m_result.scalars().all():
            model_map[m.id] = m.name

    # 批量查用户名
    from app.models.user import User as UserModel
    user_ids = list({log.user_id for log in logs})
    user_map: dict = {}
    if user_ids:
        u_result = await db.execute(select(UserModel).where(UserModel.id.in_(user_ids)))
        for u in u_result.scalars().all():
            user_map[u.id] = u.name or u.user_code

    items = [
        {
            "id": log.id,
            "model_config_id": log.model_config_id,
            "model_name": model_map.get(log.model_config_id, "未知"),
            "user_id": log.user_id,
            "username": user_map.get(log.user_id, "未知"),
            "usage_type": log.usage_type,
            "input_tokens": log.input_tokens,
            "output_tokens": log.output_tokens,
            "total_tokens": log.input_tokens + log.output_tokens,
            "audio_seconds": log.audio_seconds,
            "latency_ms": log.latency_ms,
            "estimated_cost": round(log.estimated_cost, 6),
            "is_success": log.is_success,
            "error_message": log.error_message,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]

    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    }


# ==================== 使用统计 ====================

@router.get("/usage-stats", summary="获取模型使用统计")
async def get_model_usage_stats(
    range: str = Query("week", description="统计范围: day/week/month"),
    model_id: Optional[int] = Query(None, description="指定模型ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取 AI 模型使用统计（仅管理员）
    """
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可查看")
    
    # 计算时间范围
    now = datetime.utcnow()
    if range == "day":
        start_date = now - timedelta(days=1)
    elif range == "week":
        start_date = now - timedelta(days=7)
    else:
        start_date = now - timedelta(days=30)
    
    # 查询使用日志
    stmt = select(AIModelUsageLog).where(AIModelUsageLog.created_at >= start_date)
    
    if model_id:
        stmt = stmt.where(AIModelUsageLog.model_config_id == model_id)
    
    result = await db.execute(stmt)
    logs = list(result.scalars().all())
    
    # 统计
    total_calls = len(logs)
    total_tokens = sum(log.input_tokens + log.output_tokens for log in logs)
    total_cost = sum(log.estimated_cost for log in logs)
    success_count = sum(1 for log in logs if log.is_success)
    avg_latency = sum(log.latency_ms for log in logs) / total_calls if total_calls > 0 else 0
    
    # 按模型分组统计
    model_stats = {}
    for log in logs:
        mid = log.model_config_id
        if mid not in model_stats:
            model_stats[mid] = {
                "calls": 0,
                "tokens": 0,
                "cost": 0,
                "successes": 0
            }
        model_stats[mid]["calls"] += 1
        model_stats[mid]["tokens"] += log.input_tokens + log.output_tokens
        model_stats[mid]["cost"] += log.estimated_cost
        if log.is_success:
            model_stats[mid]["successes"] += 1
    
    # 补充模型名称
    for mid in model_stats:
        model = await db.get(AIModelConfig, mid)
        if model:
            model_stats[mid]["model_name"] = model.name
            model_stats[mid]["provider"] = model.provider
    
    return {
        "success": True,
        "data": {
            "summary": {
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "success_rate": round(success_count / total_calls, 4) if total_calls > 0 else 0,
                "avg_latency_ms": round(avg_latency, 2)
            },
            "by_model": model_stats,
            "range": range,
            "start_date": start_date.isoformat(),
            "end_date": now.isoformat()
        }
    }
