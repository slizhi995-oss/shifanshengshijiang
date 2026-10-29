"""Test profile API response format"""
import asyncio
import sys
import json
sys.path.insert(0, "/app")

from app.core.database import async_session_factory
from app.services.profile_service import profile_service

async def test():
    async with async_session_factory() as db:
        # Test with student_id=2 (first student in seed data)
        profile = await profile_service.compute_student_profile(db, 2, None)
        
        print("=== RADAR ===")
        radar = profile.get("radar", [])
        print(f"Type: {type(radar).__name__}, Length: {len(radar)}")
        if radar:
            print(f"First item: {json.dumps(radar[0], ensure_ascii=False)}")
            categories = set(d.get("category") for d in radar)
            print(f"Categories: {categories}")
            for cat in categories:
                dims = [d for d in radar if d.get("category") == cat]
                print(f"  {cat}: {len(dims)} dims, scores: {[d['score'] for d in dims]}")
        
        print("\n=== TREND ===")
        trend = profile.get("trend", [])
        print(f"Length: {len(trend)}")
        if trend:
            print(f"First: {json.dumps(trend[0], ensure_ascii=False)}")
            print(f"Has overall_score: {'overall_score' in trend[0]}")
        
        print(f"\n=== STATS ===")
        print(json.dumps(profile.get("stats", {}), ensure_ascii=False))
        print(f"Overall score: {profile.get('overall_score')}")
        
        print(f"\n=== ACTION ITEMS ===")
        items = profile.get("action_items", [])
        print(f"Count: {len(items)}")
        for item in items[:3]:
            print(f"  - {item.get('dimension')}: {item.get('suggestion', '')[:60]}...")

asyncio.run(test())
