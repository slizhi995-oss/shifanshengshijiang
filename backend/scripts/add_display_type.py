"""
Migration script to add display_type column to notices table.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine


async def add_display_type_column():
    """Add display_type column to notices table if not exists."""
    print("Adding display_type column to notices table...")
    
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'notices' 
            AND column_name = 'display_type'
        """))
        exists = result.scalar()
        
        if exists:
            print("Column 'display_type' already exists. Skipping.")
        else:
            await conn.execute(text("""
                ALTER TABLE notices 
                ADD COLUMN display_type VARCHAR(20) DEFAULT 'dialog'
            """))
            print("Column 'display_type' added successfully!")
    
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(add_display_type_column())
