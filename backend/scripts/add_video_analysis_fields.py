"""
添加视频分析相关字段到 submissions 表
支持 MySQL 和 SQLite
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine
from app.core.config import settings


async def check_column_exists_mysql(conn, table_name: str, column_name: str) -> bool:
    """检查 MySQL 表中是否存在指定字段"""
    result = await conn.execute(
        text(f"""
            SELECT COUNT(*) 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = :table_name 
            AND COLUMN_NAME = :column_name
        """),
        {"table_name": table_name, "column_name": column_name}
    )
    count = result.scalar()
    return count > 0


async def check_column_exists_sqlite(conn, table_name: str, column_name: str) -> bool:
    """检查 SQLite 表中是否存在指定字段"""
    result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    columns = [row[1] for row in result.fetchall()]
    return column_name in columns


async def add_video_analysis_fields():
    """添加视频分析相关字段"""
    # 判断数据库类型
    is_mysql = "mysql" in settings.DATABASE_URL.lower()
    
    print("=" * 60)
    print("添加视频分析字段到 submissions 表")
    print("=" * 60)
    print(f"数据库类型: {'MySQL' if is_mysql else 'SQLite'}")
    print()
    
    async with engine.begin() as conn:
        try:
            # 定义要添加的字段
            fields = [
                ("lesson_plan_analysis", "TEXT", "教案AI分析结果(JSON)"),
                ("video_analysis", "TEXT", "视频AI分析结果(JSON)"),
                ("ai_suggested_feedback", "TEXT", "AI建议评语"),
                ("ai_suggested_score", "FLOAT" if is_mysql else "REAL", "AI建议分数"),
            ]
            
            for field_name, field_type, comment in fields:
                # 检查字段是否存在
                if is_mysql:
                    exists = await check_column_exists_mysql(conn, "submissions", field_name)
                else:
                    exists = await check_column_exists_sqlite(conn, "submissions", field_name)
                
                if exists:
                    print(f"⏭️  字段已存在: {field_name}")
                else:
                    # 添加字段
                    if is_mysql:
                        sql = f"ALTER TABLE submissions ADD COLUMN {field_name} {field_type} COMMENT '{comment}'"
                    else:
                        sql = f"ALTER TABLE submissions ADD COLUMN {field_name} {field_type}"
                    
                    await conn.execute(text(sql))
                    print(f"✅ 添加字段: {field_name} ({field_type})")
            
            print()
            print("=" * 60)
            print("🎉 数据库字段添加完成！")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(add_video_analysis_fields())
