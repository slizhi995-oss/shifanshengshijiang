"""
Authentication API routes.
Handles login and forced password change logic.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_password, hash_password, create_access_token
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import (
    UserLogin,
    TokenResponse,
    PasswordChange,
    UserResponse,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    用户登录接口。
    
    - 验证工号/学号和密码
    - 返回 JWT Token 和 is_default_password 状态
    - 前端根据 is_default_password 判断是否强制修改密码
    """
    # 查询用户
    result = await db.execute(
        select(User).where(User.user_code == login_data.user_code)
    )
    user = result.scalar_one_or_none()
    
    # 验证用户存在性和密码
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    
    # 检查用户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )
    
    # 生成 JWT Token
    access_token = create_access_token(
        subject=user.id,
        extra_data={
            "role": user.role.value,
            "user_code": user.user_code,
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        is_default_password=user.is_default_password,
        user=UserResponse.model_validate(user),
    )


@router.post("/change-password", summary="修改密码")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    修改密码接口。
    
    - 首次登录强制修改密码时调用
    - 验证旧密码，设置新密码
    - 将 is_default_password 设为 False
    """
    # 验证新密码一致性
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="两次输入的新密码不一致",
        )
    
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误",
        )
    
    # 新密码不能与旧密码相同
    if password_data.new_password == password_data.old_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与旧密码相同",
        )
    
    # 更新密码和 is_default_password 状态
    current_user.password_hash = hash_password(password_data.new_password)
    current_user.is_default_password = False
    
    await db.commit()
    
    return {"message": "密码修改成功"}


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """获取当前登录用户的详细信息。"""
    return UserResponse.model_validate(current_user)


@router.post("/refresh-token", summary="刷新Token")
async def refresh_token(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    刷新 JWT Token。
    使用当前有效的 Token 获取新的 Token。
    """
    access_token = create_access_token(
        subject=current_user.id,
        extra_data={
            "role": current_user.role.value,
            "user_code": current_user.user_code,
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
