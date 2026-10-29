
import asyncio
from app.core.database import engine
from sqlalchemy import inspect

async def check_db():
    async with engine.connect() as conn:
        def get_all_info(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            res = {}
            for table in tables:
                cols = [c['name'] for c in inspector.get_columns(table)]
                res[table] = cols
            return res
        
        info = await conn.run_sync(get_all_info)
        for table, cols in info.items():
            print(f"Table: {table}")
            print(f"  Columns: {cols}")

if __name__ == "__main__":
    asyncio.run(check_db())
