"""
Database initialization script.
Creates tables and seeds default admin user.

Usage:
    python -m scripts.init_db
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import engine, async_session_factory
from app.core.security import hash_password
from app.models.base import Base
from app.models.user import User, UserRole


async def init_database():
    """Initialize database tables."""
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!") 


async def seed_admin():
    """Create default admin user if not exists."""
    print("Checking for admin user...")
    
    async with async_session_factory() as session:
        # Check if admin exists
        result = await session.execute(
            select(User).where(User.role == UserRole.ADMIN)
        )
        existing_admin = result.scalar_one_or_none()
        
        if existing_admin:
            print(f"Admin user already exists: {existing_admin.user_code}")
            return
        
        # Create default super admin (常驻默认账号，不强制首次改密)
        admin = User(
            user_code="admin",
            name="系统管理员",
            role=UserRole.ADMIN,
            password_hash=hash_password("admin123"),
            is_default_password=False,
            is_active=True,
            is_super_admin=True,  # 设置为超级管理员
        )
        
        session.add(admin)
        await session.commit()
        
        print("Default super admin created!")
        print("  User Code: admin")
        print("  Password: admin123")
        print("  Role: Super Administrator")


async def main():
    """Main initialization function."""
    print("=" * 50)
    print("Database Initialization")
    print("=" * 50)
    
    await init_database()
    await seed_admin()
    
    print("=" * 50)
    print("Initialization complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
