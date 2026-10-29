"""
Group model for managing instructor-student-semester relationships.
"""
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.semester import Semester


class Group(Base):
    """
    Group table - records the relationship between instructor, student, and semester.
    
    Business rule: A student can only be assigned to ONE instructor per semester.
    This is enforced by the unique constraint on (semester_id, student_id).
    """
    __tablename__ = "groups"
    
    # 批次ID
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False,
        comment="批次ID"
    )
    
    # 指导老师ID
    instructor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="指导老师ID"
    )
    
    # 学生ID
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="学生ID"
    )
    
    # ==================== Unique Constraint ====================
    # 确保一个学生在一个批次内只能绑定一个指导老师
    __table_args__ = (
        UniqueConstraint(
            "semester_id", 
            "student_id", 
            name="uq_semester_student"
        ),
    )
    
    # ==================== Relationships ====================
    
    semester: Mapped["Semester"] = relationship(
        "Semester",
        back_populates="groups"
    )
    
    instructor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[instructor_id],
        back_populates="instructor_groups"
    )
    
    student: Mapped["User"] = relationship(
        "User",
        foreign_keys=[student_id],
        back_populates="student_groups"
    )
    
    def __repr__(self) -> str:
        return f"<Group(id={self.id}, semester={self.semester_id}, instructor={self.instructor_id}, student={self.student_id})>"
