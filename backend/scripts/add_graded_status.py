"""
Migration script to add 'graded' status to submissions table.
This allows separating grading from approval.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine


async def add_graded_status():
    """Add 'graded' value to submissions.status enum."""
    print("Adding 'graded' status to submissions table...")
    
    async with engine.begin() as conn:
        # Check current enum values
        result = await conn.execute(text("""
            SELECT COLUMN_TYPE 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'submissions' 
            AND column_name = 'status'
        """))
        current_type = result.scalar()
        
        if current_type and 'graded' in current_type.lower():
            print("Status 'graded' already exists. Skipping.")
        else:
            # Modify enum to include 'graded'
            await conn.execute(text("""
                ALTER TABLE submissions 
                MODIFY COLUMN status ENUM('pending', 'graded', 'approved', 'rejected') 
                DEFAULT 'pending'
            """))
            print("Status 'graded' added successfully!")
    
    print("Migration complete!")


if __name__ == "__main__":
    asyncio.run(add_graded_status())
