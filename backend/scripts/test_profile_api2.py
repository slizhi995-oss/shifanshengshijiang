"""Test profile: find students with submissions and verify profile data"""
import asyncio
import sys
import json
sys.path.insert(0, "/app")

from app.core.database import async_session_factory
from app.services.profile_service import profile_service
from sqlalchemy import select, func
from app.models.submission import Submission
from app.models.user import User, UserRole

async def test():
    async with async_session_factory() as db:
        # Find students with submissions
        r = await db.execute(
            select(Submission.student_id, func.count().label('cnt'))
            .group_by(Submission.student_id)
            .order_by(func.count().desc())
        )
        rows = r.fetchall()
        print("Students with submissions:")
        for row in rows:
            print(f"  student_id={row[0]}, submissions={row[1]}")
        
        if not rows:
            print("No submissions found!")
            return
        
        # Test with the student who has most submissions
        sid = rows[0][0]
        print(f"\n=== Testing student_id={sid} ===")
        profile = await profile_service.compute_student_profile(db, sid, None)
        
        print(f"\nRadar type: {type(profile['radar']).__name__}, len: {len(profile['radar'])}")
        if profile['radar']:
            for d in profile['radar']:
                print(f"  {d['category']}/{d['key']}: {d['label']} = {d['score']}")
        
        print(f"\nTrend len: {len(profile['trend'])}")
        for t in profile['trend'][:3]:
            print(f"  date={t.get('date')}, overall_score={t.get('overall_score')}, total_score={t.get('total_score')}")
        
        print(f"\nOverall score: {profile['overall_score']}")
        print(f"Stats: {json.dumps(profile['stats'], ensure_ascii=False)}")
        
        print(f"\nAction items: {len(profile['action_items'])}")
        for item in profile['action_items'][:3]:
            print(f"  [{item.get('priority')}] {item.get('dimension')}: {item.get('suggestion','')[:80]}")

asyncio.run(test())
