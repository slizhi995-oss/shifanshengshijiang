
import asyncio
from app.core.database import engine
from sqlalchemy import inspect
from app.models.base import Base

# Import all models to ensure they are registered in Base.metadata
from app.models.user import User
from app.models.semester import Semester
from app.models.group import Group
from app.models.task import Task
from app.models.submission import Submission
from app.models.notice import Notice
from app.models.message import Message

async def check_missing_tables():
    async with engine.connect() as conn:
        def get_existing_tables(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names()
        
        existing_tables = await conn.run_sync(get_existing_tables)
        print(f"Existing tables: {existing_tables}")
        
        expected_tables = Base.metadata.tables.keys()
        print(f"Expected tables: {list(expected_tables)}")
        
        missing = [t for t in expected_tables if t not in existing_tables]
        print(f"Missing tables: {missing}")
        
        if missing:
            print("Action: Need to create missing tables.")
            # We can't easily create individual tables via create_all if some already exist
            # but we can try to run create_all and it should skip existing ones if using sync
            # however Base.metadata.create_all is sync and needs to be run in run_sync
            return True
        return False

if __name__ == "__main__":
    asyncio.run(check_missing_tables())
