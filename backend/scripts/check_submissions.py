"""Quick check: count submissions in database"""
import asyncio
import sys
sys.path.insert(0, "/app")

from app.core.database import async_session_factory
from sqlalchemy import select, func
from app.models.submission import Submission
from app.models.user import User, UserRole

async def check():
    async with async_session_factory() as s:
        r = await s.execute(select(func.count()).select_from(Submission))
        print(f"Total submissions: {r.scalar()}")
        
        # Check submissions with scores
        r2 = await s.execute(
            select(func.count()).select_from(Submission).where(Submission.total_score.isnot(None))
        )
        print(f"Submissions with scores: {r2.scalar()}")
        
        # Check submissions with AI analysis
        r3 = await s.execute(
            select(func.count()).select_from(Submission).where(Submission.lesson_plan_analysis.isnot(None))
        )
        print(f"Submissions with lesson_plan_analysis: {r3.scalar()}")
        
        r4 = await s.execute(
            select(func.count()).select_from(Submission).where(Submission.video_analysis.isnot(None))
        )
        print(f"Submissions with video_analysis: {r4.scalar()}")
        
        # Count students
        r5 = await s.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.STUDENT)
        )
        print(f"Total students: {r5.scalar()}")

asyncio.run(check())
