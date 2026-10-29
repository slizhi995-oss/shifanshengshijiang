"""Clear all profile snapshots to force recomputation"""
import asyncio
import sys
sys.path.insert(0, "/app")

from app.core.database import async_session_factory
from sqlalchemy import text

async def clear():
    async with async_session_factory() as s:
        await s.execute(text("DELETE FROM profile_snapshots"))
        await s.commit()
        print("Cleared all profile snapshots")

asyncio.run(clear())
