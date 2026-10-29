"""
Seed submissions with scores + AI analysis for ALL students
so the growth profile and AI comparison features have data.
"""
import asyncio
import sys
import json
import random
from datetime import datetime, timedelta

sys.path.insert(0, "/app")

from app.core.database import async_session_factory
from sqlalchemy import select, func, text
from app.models.user import User, UserRole
from app.models.submission import Submission, SubmissionStatus
from app.models.task import Task
from app.models.group import Group

random.seed(42)

# AI 教案分析模板
def make_lesson_plan_analysis(base_score):
    dims = {}
    for key in ["structure", "objectives", "key_points", "teaching_process", "teaching_methods", "board_design", "language"]:
        offset = random.randint(-8, 8)
        score = max(40, min(100, base_score + offset))
        dims[key] = {
            "score": score,
            "feedback": f"该维度得分{score}分" 
        }
    overall = round(sum(d["score"] for d in dims.values()) / len(dims), 1)
    return json.dumps({
        "overall_score": overall,
        "dimensions": dims,
        "summary": f"教案整体质量{'优秀' if overall >= 85 else '良好' if overall >= 75 else '中等'}，综合得分{overall}分。"
    }, ensure_ascii=False)

# AI 视频分析模板
def make_video_analysis(base_score):
    speech_rate = random.randint(110, 180)
    filler = random.randint(0, 8)
    pause = random.randint(0, 3)
    gesture_base = max(40, min(100, base_score + random.randint(-10, 5)))
    return json.dumps({
        "speech_rate": speech_rate,
        "filler_word_count": filler,
        "pause_count": pause,
        "gesture_analysis": {
            "gesture_score": max(40, min(100, gesture_base + random.randint(-5, 5))),
            "posture_score": max(40, min(100, gesture_base + random.randint(-5, 5))),
            "eye_contact_score": max(40, min(100, gesture_base + random.randint(-5, 5))),
            "movement_score": max(40, min(100, gesture_base + random.randint(-5, 5)))
        },
        "summary": f"语速{speech_rate}字/分钟，语气词{filler}次。"
    }, ensure_ascii=False)


async def seed():
    async with async_session_factory() as db:
        # 1. Get all students
        result = await db.execute(
            select(User).where(User.role == UserRole.STUDENT).order_by(User.id)
        )
        students = list(result.scalars().all())
        print(f"Found {len(students)} students")

        # 2. Get semesters
        from app.models.semester import Semester
        sem_result = await db.execute(select(Semester).order_by(Semester.id))
        semesters = list(sem_result.scalars().all())
        if not semesters:
            print("No semesters found! Cannot seed.")
            return
        semester = semesters[0]
        print(f"Using semester: {semester.name} (id={semester.id})")

        # 3. Get tasks for this semester
        task_result = await db.execute(
            select(Task).where(Task.semester_id == semester.id).order_by(Task.id)
        )
        tasks = list(task_result.scalars().all())
        if not tasks:
            print("No tasks found for this semester! Creating a demo task...")
            # Find an instructor
            instr_result = await db.execute(
                select(User).where(User.role == UserRole.INSTRUCTOR).limit(1)
            )
            instructor = instr_result.scalar_one_or_none()
            if not instructor:
                print("No instructor found!")
                return
            
            for i, title in enumerate(["小学数学：分数的认识", "初中语文：春", "高中英语：Unit 5 Reading"]):
                t = Task(
                    title=title,
                    description=f"请完成{title}的试讲教案和视频录制",
                    semester_id=semester.id,
                    instructor_id=instructor.id,
                    is_published=True,
                    deadline=datetime.now() + timedelta(days=30),
                )
                db.add(t)
            await db.commit()
            
            task_result = await db.execute(
                select(Task).where(Task.semester_id == semester.id).order_by(Task.id)
            )
            tasks = list(task_result.scalars().all())
        
        print(f"Tasks: {[t.title for t in tasks]}")

        # 4. Seed submissions for students without any
        seeded = 0
        for student in students:
            # Check existing submissions
            existing = await db.execute(
                select(func.count()).select_from(Submission).where(Submission.student_id == student.id)
            )
            if existing.scalar() > 0:
                print(f"  {student.name or student.user_code}: already has submissions, skipping")
                continue

            # Create 3-5 submissions with increasing scores (growth trend)
            num_subs = random.randint(3, 5)
            base_score = random.randint(60, 75)  # starting score
            growth = random.uniform(2, 5)  # points per submission

            for i in range(num_subs):
                task = tasks[i % len(tasks)]
                score = min(98, round(base_score + growth * i + random.uniform(-3, 3), 1))
                
                lp_score = round(score * random.uniform(0.9, 1.1), 1)
                v_score = round(score * random.uniform(0.85, 1.05), 1)
                sub = Submission(
                    student_id=student.id,
                    task_id=task.id,
                    lesson_plan_path=f"/uploads/demo/{student.user_code}_sub{i+1}.pdf",
                    lesson_plan_name=f"{student.user_code}_lesson_{i+1}.pdf",
                    video_path=f"/uploads/demo/{student.user_code}_video{i+1}.mp4",
                    video_name=f"{student.user_code}_video_{i+1}.mp4",
                    status=SubmissionStatus.APPROVED if i < num_subs - 1 else random.choice([SubmissionStatus.APPROVED, SubmissionStatus.PENDING]),
                    total_score=score,
                    lesson_plan_score=lp_score,
                    video_score=v_score,
                    ai_suggested_score=round(score + random.uniform(-5, 5), 1),
                    lesson_plan_analysis=make_lesson_plan_analysis(round(score)),
                    video_analysis=make_video_analysis(round(score)),
                    feedback=f"overall good" if random.random() > 0.3 else None,
                    created_at=datetime.now() - timedelta(days=(num_subs - i) * 7 + random.randint(0, 3)),
                )
                db.add(sub)
            
            seeded += 1
            print(f"  {student.name or student.user_code}: seeded {num_subs} submissions (base={base_score})")

        await db.commit()
        print(f"\nDone! Seeded submissions for {seeded} students.")

        # 5. Clear profile snapshots to force recomputation
        await db.execute(text("DELETE FROM profile_snapshots"))
        await db.commit()
        print("Cleared profile snapshots.")

asyncio.run(seed())
