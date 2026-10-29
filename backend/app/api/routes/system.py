"""
System settings API routes.
Handles system configuration and file uploads.
"""
import os
import json
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pathlib import Path

from app.core.deps import require_admin
from app.models.user import User

router = APIRouter()

# 设置存储目录
UPLOAD_DIR = Path("uploads")
SYSTEM_UPLOAD_DIR = UPLOAD_DIR / "system"
SYSTEM_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 持久化存储文件
SETTINGS_FILE = SYSTEM_UPLOAD_DIR / "settings.json"

# 默认系统设置
DEFAULT_SETTINGS = {
    "site_name": "智教领航",
    "site_logo_url": "",
    "login_bg_url": "",
    "school_name": "高校师范",
    "default_avatar_url": "",
    "footer_text": ""
}


def _load_settings() -> dict:
    """从 JSON 文件加载设置，文件不存在则返回默认值"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 合并默认值，防止字段缺失
                return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def _save_settings(settings: dict) -> None:
    """将设置持久化到 JSON 文件"""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


class SystemSettings(BaseModel):
    """系统设置schema"""
    site_name: str = Field(..., description="网站名称")
    site_logo_url: str = Field(default="", description="网站Logo URL")
    login_bg_url: str = Field(default="", description="登录页背景图URL")
    school_name: str = Field(..., description="学校名称")
    default_avatar_url: str = Field(default="", description="默认用户头像URL")
    footer_text: str = Field(default="", description="页脚文字")


@router.get(
    "/public-settings",
    summary="获取公开系统设置（无需登录）"
)
async def get_public_settings():
    """返回无需鉴权的公开设置：网站名称、学校名称等。"""
    s = _load_settings()
    return {
        "site_name": s.get("site_name", DEFAULT_SETTINGS["site_name"]),
        "school_name": s.get("school_name", DEFAULT_SETTINGS["school_name"]),
        "site_logo_url": s.get("site_logo_url", ""),
        "footer_text": s.get("footer_text", ""),
    }


@router.get(
    "/settings",
    response_model=SystemSettings,
    summary="获取系统设置"
)
async def get_system_settings(
    current_user: User = Depends(require_admin),
) -> SystemSettings:
    """获取系统设置，仅管理员可访问。"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员才能访问系统设置"
        )
    return SystemSettings(**_load_settings())


@router.put(
    "/settings",
    response_model=SystemSettings,
    summary="更新系统设置"
)
async def update_system_settings(
    settings: SystemSettings,
    current_user: User = Depends(require_admin),
) -> SystemSettings:
    """更新系统设置，仅超级管理员可用。"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员才能修改系统设置"
        )
    
    new_settings = settings.model_dump()
    _save_settings(new_settings)
    return SystemSettings(**new_settings)


async def save_upload_file(file: UploadFile, subdir: str) -> str:
    """保存上传的文件并返回URL"""
    # 生成唯一文件名
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    import time
    filename = f"{int(time.time())}_{file.filename}"
    
    # 创建子目录
    upload_path = SYSTEM_UPLOAD_DIR / subdir
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    file_path = upload_path / filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 返回相对URL
    return f"/uploads/system/{subdir}/{filename}"


@router.post(
    "/upload/logo",
    summary="上传网站Logo"
)
async def upload_logo(
    file: UploadFile = File(..., description="Logo图片文件"),
    current_user: User = Depends(require_admin),
) -> JSONResponse:
    """上传网站Logo，仅超级管理员可用。"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员才能上传系统资源"
        )
    
    # 验证文件类型
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传图片文件"
        )
    
    url = await save_upload_file(file, "logo")
    return JSONResponse(content={"url": url})


@router.post(
    "/upload/background",
    summary="上传登录页背景图"
)
async def upload_background(
    file: UploadFile = File(..., description="背景图片文件"),
    current_user: User = Depends(require_admin),
) -> JSONResponse:
    """上传登录页背景图，仅超级管理员可用。"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员才能上传系统资源"
        )
    
    # 验证文件类型
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传图片文件"
        )
    
    url = await save_upload_file(file, "background")
    return JSONResponse(content={"url": url})


@router.post(
    "/upload/avatar",
    summary="上传默认用户头像"
)
async def upload_avatar(
    file: UploadFile = File(..., description="头像图片文件"),
    current_user: User = Depends(require_admin),
) -> JSONResponse:
    """上传默认用户头像，仅超级管理员可用。"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有超级管理员才能上传系统资源"
        )
    
    # 验证文件类型
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传图片文件"
        )
    
    url = await save_upload_file(file, "avatar")
    return JSONResponse(content={"url": url})
