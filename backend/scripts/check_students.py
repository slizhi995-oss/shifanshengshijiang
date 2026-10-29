"""Check student accounts and their submissions"""
import asyncio
import sys
sys.path.insert(0, "/app")

from app.core.database import async_session_factory
from sqlalchemy import select, func
from app.models.user import User, UserRole
from app.models.submission import Submission

async def check():
    async with async_session_factory() as db:
        # All students
        result = await db.execute(
            select(User.id, User.user_code, User.name, User.college)
            .where(User.role == UserRole.STUDENT)
            .order_by(User.id)
        )
        students = result.fetchall()
        
        # Submissions per student
        sub_result = await db.execute(
            select(Submission.student_id, func.count().label('cnt'))
            .group_by(Submission.student_id)
        )
        sub_map = {r[0]: r[1] for r in sub_result.fetchall()}
        
        print(f"{'ID':<5} {'学号':<15} {'姓名':<10} {'学院':<15} {'提交数':<5}")
        print("-" * 55)
        for s in students:
            cnt = sub_map.get(s[0], 0)
            marker = " ✓" if cnt > 0 else ""
            print(f"{s[0]:<5} {s[1] or '':<15} {s[2] or '':<10} {s[3] or '':<15} {cnt:<5}{marker}")

asyncio.run(check())
