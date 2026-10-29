"""
Migration script to add attachment_path column to notices table.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine


async def add_attachment_path_column():
    """Add attachment_path column to notices table if not exists."""
    print("Checking attachment_path column in notices table...")
    
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'notices' 
            AND column_name = 'attachment_path'
        """))
        exists = result.scalar()
        
        if exists:
            print("Column 'attachment_path' already exists. Skipping.")
        else:
            await conn.execute(text("""
                ALTER TABLE notices 
                ADD COLUMN attachment_path VARCHAR(512) DEFAULT NULL
            """))
            print("Column 'attachment_path' added successfully!")
    
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(add_attachment_path_column())
