
import asyncio
from app.core.database import engine, Base
# Import all models to register them
import app.models  # This should trigger all imports in __init__.py

async def force_init():
    print("Forcing full database initialization...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Full database initialization completed.")

if __name__ == "__main__":
    asyncio.run(force_init())
