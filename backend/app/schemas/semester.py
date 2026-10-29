"""
Semester-related Pydantic schemas.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.semester import SemesterStatus


class SemesterBase(BaseModel):
    """Base semester schema."""
    name: str = Field(..., min_length=2, max_length=128, description="批次名称")
    description: Optional[str] = Field(default=None, description="批次描述")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('批次名称至少需要2个字符')
        if len(v) > 128:
            raise ValueError('批次名称不能超过128个字符')
        return v.strip()


class SemesterCreate(SemesterBase):
    """Schema for creating a semester."""
    pass


class SemesterUpdate(BaseModel):
    """Schema for updating a semester."""
    name: Optional[str] = Field(default=None, max_length=128, description="批次名称")
    description: Optional[str] = Field(default=None, description="批次描述")
    status: Optional[SemesterStatus] = Field(default=None, description="批次状态")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            if len(v.strip()) < 2:
                raise ValueError('批次名称至少需要2个字符')
            if len(v) > 128:
                raise ValueError('批次名称不能超过128个字符')
            return v.strip()
        return v


class SemesterResponse(BaseModel):
    """Semester response schema."""
    id: int = Field(..., description="批次ID")
    name: str = Field(..., description="批次名称")
    status: SemesterStatus = Field(..., description="批次状态")
    description: Optional[str] = Field(default=None, description="批次描述")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 统计信息
    student_count: Optional[int] = Field(default=None, description="学生数量")
    instructor_count: Optional[int] = Field(default=None, description="指导老师数量")
    
    model_config = {"from_attributes": True}
