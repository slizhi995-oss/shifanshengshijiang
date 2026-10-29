"""
User-related Pydantic schemas.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.user import UserRole


# ==================== Auth Schemas ====================

class UserLogin(BaseModel):
    """Login request schema."""
    user_code: str = Field(..., min_length=1, max_length=32, description="工号/学号")
    password: str = Field(..., min_length=1, description="密码")


class TokenResponse(BaseModel):
    """Login response with token and user info."""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    is_default_password: bool = Field(..., description="是否为默认密码")
    user: "UserResponse" = Field(..., description="用户信息")


class PasswordChange(BaseModel):
    """Password change request schema."""
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=32, description="新密码")
    confirm_password: str = Field(..., min_length=6, max_length=32, description="确认新密码")


# ==================== User CRUD Schemas ====================

class UserBase(BaseModel):
    """Base user schema with common fields."""
    user_code: str = Field(..., min_length=1, max_length=32, description="工号/学号")
    name: str = Field(..., min_length=1, max_length=64, description="姓名")
    role: UserRole = Field(..., description="用户角色")
    email: Optional[str] = Field(default=None, description="邮箱")
    phone: Optional[str] = Field(default=None, max_length=20, description="手机号")
    remark: Optional[str] = Field(default=None, description="备注")
    college: Optional[str] = Field(default=None, description="学院")
    major: Optional[str] = Field(default=None, description="专业")
    class_name: Optional[str] = Field(default=None, description="班级")
    head_teacher: Optional[str] = Field(default=None, description="班主任")


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: Optional[str] = Field(default=None, description="密码(默认为工号)")


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    name: Optional[str] = Field(default=None, max_length=64, description="姓名")
    email: Optional[str] = Field(default=None, description="邮箱")
    phone: Optional[str] = Field(default=None, max_length=20, description="手机号")
    remark: Optional[str] = Field(default=None, description="备注")
    is_active: Optional[bool] = Field(default=None, description="是否启用")
    college: Optional[str] = Field(default=None, description="学院")
    major: Optional[str] = Field(default=None, description="专业")
    class_name: Optional[str] = Field(default=None, description="班级")
    head_teacher: Optional[str] = Field(default=None, description="班主任")


class AdminCreate(BaseModel):
    """Schema for creating an admin user."""
    user_code: str = Field(..., min_length=1, max_length=32, description="管理员账号")
    name: str = Field(..., min_length=1, max_length=64, description="管理员姓名")
    college: str = Field(..., min_length=1, description="学院名称")
    password: str = Field(..., min_length=6, max_length=32, description="密码（至少6位）")


class UserResponse(BaseModel):
    """User response schema."""
    id: int = Field(..., description="用户ID")
    user_code: str = Field(..., description="工号/学号")
    name: str = Field(..., description="姓名")
    role: UserRole = Field(..., description="用户角色")
    is_default_password: bool = Field(..., description="是否为默认密码")
    is_active: bool = Field(..., description="是否启用")
    is_super_admin: bool = Field(default=False, description="是否为超级管理员")
    email: Optional[str] = Field(default=None, description="邮箱")
    phone: Optional[str] = Field(default=None, description="手机号")
    avatar: Optional[str] = Field(default=None, description="头像URL")
    remark: Optional[str] = Field(default=None, description="备注")
    college: Optional[str] = Field(default=None, description="学院")
    major: Optional[str] = Field(default=None, description="专业")
    class_name: Optional[str] = Field(default=None, description="班级")
    head_teacher: Optional[str] = Field(default=None, description="班主任")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = {"from_attributes": True}


# ==================== Import Schemas ====================

class UserImportItem(BaseModel):
    """Single item for batch user import from Excel."""
    user_code: str = Field(..., description="工号/学号")
    name: str = Field(..., description="姓名")
    role: UserRole = Field(..., description="角色")


class UserImportRequest(BaseModel):
    """Batch user import request."""
    users: List[UserImportItem] = Field(..., min_length=1, description="用户列表")


class UserImportResult(BaseModel):
    """Batch user import result."""
    success_count: int = Field(..., description="成功导入数量")
    fail_count: int = Field(..., description="失败数量")
    failed_items: List[dict] = Field(default_factory=list, description="失败项详情")


# Forward reference update
TokenResponse.model_rebuild()
