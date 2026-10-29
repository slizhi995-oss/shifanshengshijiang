"""
Custom exception classes and handlers.
"""
from typing import Any, Optional
from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception."""
    
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: str = "请求处理失败",
        headers: Optional[dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class NotFoundException(AppException):
    """Resource not found exception."""
    
    def __init__(self, resource: str = "资源"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource}不存在",
        )


class UnauthorizedException(AppException):
    """Unauthorized access exception."""
    
    def __init__(self, detail: str = "未授权访问"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(AppException):
    """Forbidden access exception."""
    
    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ValidationException(AppException):
    """Validation error exception."""
    
    def __init__(self, detail: str = "数据验证失败"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class DuplicateException(AppException):
    """Duplicate resource exception."""
    
    def __init__(self, resource: str = "资源"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource}已存在",
        )


class FileUploadException(AppException):
    """File upload error exception."""
    
    def __init__(self, detail: str = "文件上传失败"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
