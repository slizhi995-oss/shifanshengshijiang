"""Debug: check why video fallback isn't working"""
import asyncio
import sys
import json
import hashlib
sys.path.insert(0, "/app")

from app.core.database import async_session_factory
from sqlalchemy import select
from app.models.submission import Submission

async def debug():
    async with async_session_factory() as db:
        result = await db.execute(
            select(Submission).where(Submission.student_id == 21).order_by(Submission.created_at)
        )
        subs = list(result.scalars().all())
        print(f"Student 21 has {len(subs)} submissions")
        
        video_scores = {
            "speech_rate": [], "fluency": [], "gesture": [],
            "posture": [], "eye_contact": [], "space_usage": []
        }
        
        for sub in subs:
            print(f"\nSub {sub.id}: total_score={sub.total_score}")
            print(f"  lesson_plan_analysis: {'YES' if sub.lesson_plan_analysis else 'NO'}")
            print(f"  video_analysis: {'YES' if sub.video_analysis else 'NO'}")
            
            if sub.video_analysis:
                analysis = json.loads(sub.video_analysis)
                print(f"  video_analysis keys: {list(analysis.keys())}")
                speech_rate = analysis.get("speech_rate", 0)
                print(f"  speech_rate={speech_rate}")
                gesture = analysis.get("gesture_analysis", {})
                print(f"  gesture_analysis: {gesture}")
                
                if speech_rate > 0:
                    video_scores["speech_rate"].append(80)
                filler_count = analysis.get("filler_word_count", 0)
                pause_count = analysis.get("pause_count", 0)
                fluency_score = max(0, 100 - filler_count * 5 - pause_count * 10)
                video_scores["fluency"].append(fluency_score)
                if gesture:
                    video_scores["gesture"].append(gesture.get("gesture_score", 70))
        
        print(f"\nVideo scores before fallback: {dict((k, v) for k, v in video_scores.items())}")
        
        scored_subs = [s for s in subs if s.total_score is not None and s.total_score > 0]
        print(f"Scored subs count: {len(scored_subs)}")
        
        for dim_key in video_scores:
            empty = not video_scores[dim_key]
            has_scored = bool(scored_subs)
            print(f"  {dim_key}: empty={empty}, has_scored={has_scored}, will_fallback={empty and has_scored}")
            if empty and scored_subs:
                for sub in scored_subs:
                    base = float(sub.total_score)
                    h = int(hashlib.md5(f"{sub.id}v_{dim_key}".encode()).hexdigest()[:4], 16)
                    offset = (h % 15) - 7
                    estimated = max(30, min(100, base + offset))
                    video_scores[dim_key].append(estimated)
                    print(f"    sub {sub.id}: base={base}, offset={offset}, estimated={estimated}")
        
        print(f"\nVideo scores after fallback: {dict((k, v) for k, v in video_scores.items())}")

asyncio.run(debug())
