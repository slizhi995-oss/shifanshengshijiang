"""
Seed test data for development.
Creates sample instructors, students, semesters, etc.

Usage:
    python -m scripts.seed_test_data
"""
import asyncio
import sys
from pathlib import Path
from datetime import date, datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.semester import Semester, SemesterStatus
from app.models.group import Group
from app.models.task import Task
from app.models.notice import Notice


async def seed_instructors():
    """Create sample instructors."""
    instructors_data = [
        {"user_code": "T001", "name": "张教授"},
        {"user_code": "T002", "name": "李老师"},
        {"user_code": "T003", "name": "王导师"},
    ]
    
    async with async_session_factory() as session:
        for data in instructors_data:
            result = await session.execute(
                select(User).where(User.user_code == data["user_code"])
            )
            if result.scalar_one_or_none():
                continue
            
            user = User(
                user_code=data["user_code"],
                name=data["name"],
                role=UserRole.INSTRUCTOR,
                password_hash=hash_password(data["user_code"]),
                is_default_password=True,
            )
            session.add(user)
        
        await session.commit()
    
    print(f"Created {len(instructors_data)} instructors")


async def seed_students():
    """Create sample students."""
    students_data = [
        {"user_code": "S2021001", "name": "陈小明"},
        {"user_code": "S2021002", "name": "刘小红"},
        {"user_code": "S2021003", "name": "杨小华"},
        {"user_code": "S2021004", "name": "赵小强"},
        {"user_code": "S2021005", "name": "周小丽"},
        {"user_code": "S2021006", "name": "吴小军"},
        {"user_code": "S2021007", "name": "郑小芳"},
        {"user_code": "S2021008", "name": "孙小伟"},
    ]
    
    async with async_session_factory() as session:
        for data in students_data:
            result = await session.execute(
                select(User).where(User.user_code == data["user_code"])
            )
            if result.scalar_one_or_none():
                continue
            
            user = User(
                user_code=data["user_code"],
                name=data["name"],
                role=UserRole.STUDENT,
                password_hash=hash_password(data["user_code"]),
                is_default_password=True,
            )
            session.add(user)
        
        await session.commit()
    
    print(f"Created {len(students_data)} students")


async def seed_semester():
    """Create sample semester."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Semester).where(Semester.name == "2025春季试讲")
        )
        if result.scalar_one_or_none():
            print("Semester already exists")
            return
        
        semester = Semester(
            name="2025春季试讲",
            status=SemesterStatus.ACTIVE,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            description="2025年春季学期师范生试讲训练",
        )
        session.add(semester)
        await session.commit()
    
    print("Created semester: 2025春季试讲")


async def seed_groups():
    """Assign some students to instructors."""
    async with async_session_factory() as session:
        # Get semester
        semester_result = await session.execute(
            select(Semester).where(Semester.name == "2025春季试讲")
        )
        semester = semester_result.scalar_one_or_none()
        if not semester:
            print("Semester not found, skipping groups")
            return
        
        # Get instructors
        instructors_result = await session.execute(
            select(User).where(User.role == UserRole.INSTRUCTOR)
        )
        instructors = instructors_result.scalars().all()
        
        # Get students
        students_result = await session.execute(
            select(User).where(User.role == UserRole.STUDENT)
        )
        students = students_result.scalars().all()
        
        if not instructors or not students:
            print("No instructors or students found")
            return
        
        # Assign students round-robin to instructors
        for i, student in enumerate(students):
            instructor = instructors[i % len(instructors)]
            
            # Check if already assigned
            existing = await session.execute(
                select(Group).where(
                    Group.semester_id == semester.id,
                    Group.student_id == student.id,
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            group = Group(
                semester_id=semester.id,
                instructor_id=instructor.id,
                student_id=student.id,
            )
            session.add(group)
        
        await session.commit()
    
    print("Created student-instructor assignments")


async def seed_sample_task():
    """Create a sample task."""
    async with async_session_factory() as session:
        # Get semester and first instructor
        semester_result = await session.execute(
            select(Semester).where(Semester.name == "2025春季试讲")
        )
        semester = semester_result.scalar_one_or_none()
        
        instructor_result = await session.execute(
            select(User).where(User.role == UserRole.INSTRUCTOR).limit(1)
        )
        instructor = instructor_result.scalar_one_or_none()
        
        if not semester or not instructor:
            print("Missing semester or instructor for task")
            return
        
        # Check if task exists
        existing = await session.execute(
            select(Task).where(Task.title == "第一次试讲作业")
        )
        if existing.scalar_one_or_none():
            print("Sample task already exists")
            return
        
        task = Task(
            title="第一次试讲作业",
            content="""
<h2>试讲要求</h2>
<p>请按照以下要求完成本次试讲作业：</p>
<ol>
    <li><strong>教案要求：</strong>
        <ul>
            <li>使用标准教案模板</li>
            <li>包含完整的教学目标、重难点分析</li>
            <li>教学过程设计合理</li>
        </ul>
    </li>
    <li><strong>视频要求：</strong>
        <ul>
            <li>时长10-15分钟</li>
            <li>画面清晰，声音清楚</li>
            <li>展示完整的教学片段</li>
        </ul>
    </li>
</ol>
<p><strong>截止日期：</strong>请在规定时间内提交。</p>
            """,
            semester_id=semester.id,
            instructor_id=instructor.id,
            deadline=datetime.now() + timedelta(days=14),
            require_lesson_plan=True,
            require_video=True,
            is_published=True,
        )
        session.add(task)
        await session.commit()
    
    print("Created sample task")


async def seed_notice():
    """Create a sample notice."""
    async with async_session_factory() as session:
        existing = await session.execute(
            select(Notice).where(Notice.title == "欢迎使用试讲管理系统")
        )
        if existing.scalar_one_or_none():
            print("Sample notice already exists")
            return
        
        notice = Notice(
            title="欢迎使用试讲管理系统",
            content="""
<p>亲爱的老师和同学们：</p>
<p>欢迎使用高校师范生试讲智慧管理系统！</p>
<p>本系统旨在帮助师范生更好地进行试讲训练，主要功能包括：</p>
<ul>
    <li>在线提交教案和试讲视频</li>
    <li>指导老师在线批改和反馈</li>
    <li>实时查看作业状态</li>
    <li>师生互动交流</li>
</ul>
<p>如有问题，请联系管理员。</p>
<p>祝学习愉快！</p>
            """,
            is_pinned=True,
            is_published=True,
        )
        session.add(notice)
        await session.commit()
    
    print("Created sample notice")


async def main():
    """Run all seeders."""
    print("=" * 50)
    print("Seeding Test Data")
    print("=" * 50)
    
    await seed_instructors()
    await seed_students()
    await seed_semester()
    await seed_groups()
    await seed_sample_task()
    await seed_notice()
    
    print("=" * 50)
    print("Test data seeding complete!")
    print("=" * 50)
    print("\nTest accounts created:")
    print("  Admin: admin / admin123")
    print("  Instructors: T001, T002, T003 (password = user_code)")
    print("  Students: S2021001 ~ S2021008 (password = user_code)")


if __name__ == "__main__":
    asyncio.run(main())
