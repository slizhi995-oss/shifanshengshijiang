import asyncio
import sys
import os
import random
from datetime import datetime, timedelta
from faker import Faker
from sqlalchemy import select, delete

# Ensure app can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.semester import Semester, SemesterStatus
from app.models.group import Group
from app.models.task import Task
from app.models.submission import Submission, SubmissionStatus

fake = Faker('zh_CN')

# Configuration
NUM_INSTRUCTORS = 20
NUM_STUDENTS_PER_CLASS = 40
NUM_CLASSES = 10  # Total students ~ 400
NUM_SEMESTERS = 4 # 3 past, 1 active
TASKS_PER_INSTRUCTOR = 3

COLLEGES = ["教育学院", "文学院", "数学科学学院", "外国语学院", "物理与电子工程学院"]
MAJORS = {
    "教育学院": ["学前教育", "小学教育", "特殊教育"],
    "文学院": ["汉语言文学", "历史学"],
    "数学科学学院": ["数学与应用数学", "统计学"],
    "外国语学院": ["英语", "日语"],
    "物理与电子工程学院": ["物理学", "电子信息工程"]
}

async def clear_data(session):
    print("🧹 清理旧数据...")
    # Order matters due to foreign keys
    await session.execute(delete(Submission))
    await session.execute(delete(Task))
    await session.execute(delete(Group))
    await session.execute(delete(Semester))
    # We keep the admin user
    await session.execute(delete(User).where(User.user_code != "admin"))
    await session.commit()
    print("✨ 旧数据清理完成")

async def create_users(session):
    print("👥 创建用户...")
    users = []
    
    # Instructors
    instructors = []
    for i in range(NUM_INSTRUCTORS):
        college = random.choice(COLLEGES)
        major = random.choice(MAJORS[college])
        instructor = User(
            user_code=f"T{1000+i}",
            name=fake.name(),
            role=UserRole.INSTRUCTOR,
            password_hash=hash_password("123456"),
            college=college,
            major=major,
            is_active=True
        )
        instructors.append(instructor)
    
    session.add_all(instructors)
    await session.flush() # flush to get IDs
    print(f"  - Created {len(instructors)} instructors")

    # Students
    students = []
    for class_idx in range(NUM_CLASSES):
        college = random.choice(COLLEGES)
        major = random.choice(MAJORS[college])
        class_name = f"{major}202{random.randint(1, 4)}级{random.randint(1, 3)}班"
        
        for i in range(NUM_STUDENTS_PER_CLASS):
            student = User(
                user_code=f"S{20210000 + class_idx*100 + i}",
                name=fake.name(),
                role=UserRole.STUDENT,
                password_hash=hash_password("123456"),
                college=college,
                major=major,
                class_name=class_name,
                is_active=True
            )
            students.append(student)
            
    session.add_all(students)
    await session.commit()
    print(f"  - Created {len(students)} students")
    
    return instructors, students

async def create_semesters(session):
    print("📅 创建学期...")
    semesters = []
    
    # Past semesters
    for i in range(NUM_SEMESTERS - 1):
        year = 2023 + (i // 2)
        season = "春季" if i % 2 == 0 else "秋季"
        sem = Semester(
            name=f"{year}年{season}试讲批次",
            status=SemesterStatus.COMPLETED,
            start_date=datetime(year, 3 if season=="春季" else 9, 1),
            end_date=datetime(year, 7 if season=="春季" else 1, 15),
            description=f"{year}年{season}师范生教学能力考核"
        )
        semesters.append(sem)
        
    # Active semester
    active_sem = Semester(
        name=f"2026年春季试讲批次",
        status=SemesterStatus.ACTIVE,
        start_date=datetime(2026, 3, 1),
        end_date=datetime(2026, 7, 15),
        description="当前正在进行的试讲批次"
    )
    semesters.append(active_sem)
    
    session.add_all(semesters)
    await session.commit()
    print(f"  - Created {len(semesters)} semesters")
    return semesters

async def assign_groups(session, semesters, instructors, students):
    print("🔗 分配指导分组...")
    groups = []
    
    # Randomly assign students to instructors for each semester
    for sem in semesters:
        # Shuffle students to distribute
        available_students = list(students)
        random.shuffle(available_students)
        
        # Distribute evenly
        chunk_size = len(students) // len(instructors)
        
        for i, instructor in enumerate(instructors):
            # Get my share of students
            start = i * chunk_size
            end = start + chunk_size if i < len(instructors) - 1 else len(students)
            my_students = available_students[start:end]
            
            for student in my_students:
                group = Group(
                    semester_id=sem.id,
                    instructor_id=instructor.id,
                    student_id=student.id
                )
                groups.append(group)
                
    session.add_all(groups)
    await session.commit()
    print(f"  - Created {len(groups)} group associations")

async def create_tasks_and_submissions(session, semesters, instructors, students):
    print("📝 创建任务与提交...")
    
    tasks = []
    submissions = []
    
    for sem in semesters:
        # Only active or completed semesters
        if sem.status == SemesterStatus.DRAFT:
            continue
            
        for instructor in instructors:
            # Create tasks for this instructor in this semester
            for t_idx in range(TASKS_PER_INSTRUCTOR):
                task = Task(
                    title=f"{sem.name}-{instructor.name}-任务{t_idx+1}",
                    content=fake.text(max_nb_chars=200),
                    semester_id=sem.id,
                    instructor_id=instructor.id,
                    deadline=datetime.now() + timedelta(days=30) if sem.status == SemesterStatus.ACTIVE else datetime.now() - timedelta(days=30),
                    is_published=True,
                    require_lesson_plan=True,
                    require_video=True
                )
                session.add(task)
                await session.flush() # get ID
                
                # Find students assigned to this instructor in this semester
                # Ideally query DB, but we know logic:
                # We need to find students who are grouped with this instructor in this semester
                
                # To be efficient, let's just query the relation
                group_stmt = select(Group).where(
                    Group.semester_id == sem.id,
                    Group.instructor_id == instructor.id
                )
                result = await session.execute(group_stmt)
                my_groups = result.scalars().all()
                my_student_ids = [g.student_id for g in my_groups]
                
                # Create submissions
                for stud_id in my_student_ids:
                    # Randomize submission status
                    
                    if sem.status == SemesterStatus.COMPLETED:
                        status = random.choice([SubmissionStatus.APPROVED, SubmissionStatus.APPROVED, SubmissionStatus.APPROVED, SubmissionStatus.GRADED])
                    else:
                        status = random.choice([SubmissionStatus.PENDING, SubmissionStatus.GRADED, SubmissionStatus.APPROVED, SubmissionStatus.REJECTED, None])
                    
                    if status is None: # Not submitted
                        continue
                        
                    score = random.uniform(60, 98) if status in [SubmissionStatus.GRADED, SubmissionStatus.APPROVED] else None
                    if status == SubmissionStatus.REJECTED:
                        score = random.uniform(30, 59)
                    
                    sub = Submission(
                        task_id=task.id,
                        student_id=stud_id,
                        status=status,
                        lesson_plan_path="/uploads/mock/lesson_plan.pdf",
                        lesson_plan_name="教案.pdf",
                        video_path="/uploads/mock/demo_video.mp4",
                        video_name="试讲视频.mp4",
                        student_remark=fake.sentence(),
                        total_score=round(score, 1) if score else None,
                        ai_suggested_score=round(score + random.uniform(-5, 5), 1) if score else None,
                        feedback=fake.sentence() if status != SubmissionStatus.PENDING else None,
                        submit_count=1,
                        submitted_at=datetime.now() - timedelta(days=random.randint(1, 60))
                    )
                    submissions.append(sub)
                    
                    if len(submissions) >= 500: # Batch insert
                        session.add_all(submissions)
                        await session.commit()
                        submissions = []
                        
    if submissions:
        session.add_all(submissions)
        await session.commit()
        
    print("  - Tasks and submissions created")

async def run():
    async with async_session_factory() as session:
        print("🚀 开始生成测试数据...")
        await clear_data(session)
        instructors, students = await create_users(session)
        semesters = await create_semesters(session)
        await assign_groups(session, semesters, instructors, students)
        await create_tasks_and_submissions(session, semesters, instructors, students)
        print("✅ 所有数据生成完毕！")

if __name__ == "__main__":
    asyncio.run(run())
