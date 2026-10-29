"""
File handling utilities for async file operations.
"""
import os
import uuid
import aiofiles
from typing import Optional, List, Tuple
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings


async def save_upload_file(
    file: UploadFile,
    subfolder: str,
    allowed_types: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    异步保存上传的文件。
    
    Args:
        file: 上传的文件对象
        subfolder: 子目录名 (如 'lesson_plans' 或 'videos')
        allowed_types: 允许的MIME类型列表
    
    Returns:
        (relative_path, original_filename) 元组
    
    Raises:
        HTTPException: 文件类型不允许或保存失败
    """
    # 验证文件类型
    if allowed_types and file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}",
        )
    
    # 创建上传目录
    upload_dir = os.path.join(settings.UPLOAD_DIR, subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 生成唯一文件名，保留原始扩展名
    original_filename = file.filename or "unknown"
    ext = os.path.splitext(original_filename)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    try:
        # 异步写入文件，分块处理大文件
        async with aiofiles.open(file_path, "wb") as out_file:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(chunk)
    except Exception as e:
        # 清理可能创建的部分文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件保存失败: {str(e)}",
        )
    
    # 返回相对路径和原始文件名
    relative_path = os.path.join(subfolder, unique_filename)
    return relative_path, original_filename


def delete_file(relative_path: str) -> bool:
    """
    删除文件。
    
    Args:
        relative_path: 相对于上传目录的路径
    
    Returns:
        是否删除成功
    """
    if not relative_path:
        return False
    
    full_path = os.path.join(settings.UPLOAD_DIR, relative_path)
    
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            return True
        except Exception:
            return False
    
    return False


def get_file_url(relative_path: Optional[str]) -> Optional[str]:
    """
    获取文件的访问URL。
    
    Args:
        relative_path: 相对于上传目录的路径
    
    Returns:
        文件访问URL或None
    """
    if not relative_path:
        return None
    
    # 返回相对于API的URL
    return f"/uploads/{relative_path}"
