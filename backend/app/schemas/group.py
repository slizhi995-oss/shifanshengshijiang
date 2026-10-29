"""
Group-related Pydantic schemas (instructor-student assignment).
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class GroupCreate(BaseModel):
    """Schema for creating a single group assignment."""
    semester_id: int = Field(..., description="批次ID")
    instructor_id: int = Field(..., description="指导老师ID")
    student_id: int = Field(..., description="学生ID")


class AssignmentItem(BaseModel):
    """Single assignment item for batch operation."""
    student_id: int = Field(..., description="学生ID")


class BatchAssignment(BaseModel):
    """
    Schema for batch assigning students to an instructor.
    Used for drag-and-drop or batch select assignment.
    """
    semester_id: int = Field(..., description="批次ID")
    instructor_id: int = Field(..., description="指导老师ID")
    student_ids: List[int] = Field(..., min_length=1, description="学生ID列表")


class BatchUnassignment(BaseModel):
    """Schema for batch removing student assignments."""
    semester_id: int = Field(..., description="批次ID")
    student_ids: List[int] = Field(..., min_length=1, description="学生ID列表")


class GroupResponse(BaseModel):
    """Group response schema."""
    id: int = Field(..., description="分组ID")
    semester_id: int = Field(..., description="批次ID")
    instructor_id: int = Field(..., description="指导老师ID")
    student_id: int = Field(..., description="学生ID")
    created_at: datetime = Field(..., description="创建时间")
    
    # 关联信息
    instructor: Optional[UserResponse] = Field(default=None, description="指导老师信息")
    student: Optional[UserResponse] = Field(default=None, description="学生信息")
    
    model_config = {"from_attributes": True}


class InstructorWithStudents(BaseModel):
    """Instructor with their assigned students."""
    instructor: UserResponse = Field(..., description="指导老师信息")
    students: List[UserResponse] = Field(default_factory=list, description="学生列表")
    student_count: int = Field(..., description="学生数量")


class AssignmentOverview(BaseModel):
    """Overview of assignments in a semester."""
    semester_id: int = Field(..., description="批次ID")
    total_instructors: int = Field(..., description="指导老师总数")
    total_students: int = Field(..., description="学生总数")
    assigned_students: int = Field(..., description="已分配学生数")
    unassigned_students: int = Field(..., description="未分配学生数")
    groups: List[InstructorWithStudents] = Field(default_factory=list, description="分组详情")


class AssignmentImportResult(BaseModel):
    """Result of batch assignment import."""
    success_count: int = Field(..., description="成功导入数量")
    fail_count: int = Field(..., description="失败数量")
    failed_items: List[dict] = Field(default_factory=list, description="失败项详情")


class AutoAssignRequest(BaseModel):
    """一键自动分配请求"""
    class_name: Optional[str] = Field(default=None, description="班级筛选")
    college: Optional[str] = Field(default=None, description="学院筛选")
    major: Optional[str] = Field(default=None, description="专业筛选")
    instructor_ids: List[int] = Field(default_factory=list, description="指定的老师ID列表，空则分配给所有老师")
    same_class_grouping: bool = Field(default=False, description="是否要求同组学生必须来自同一班级")
