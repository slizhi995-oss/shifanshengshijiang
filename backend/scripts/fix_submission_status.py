"""
修复 submissions 表 status 字段大小写不一致问题。
数据库中存了大写的 APPROVED/PENDING/REJECTED 等，但代码枚举定义的是小写值。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine


async def fix_status():
    async with engine.begin() as conn:
        # 先把 ENUM 列改成 VARCHAR 以便更新值
        await conn.execute(text(
            "ALTER TABLE submissions MODIFY COLUMN status VARCHAR(20) DEFAULT 'pending'"
        ))
        print("✅ 临时改为 VARCHAR")

        # 把大写值全部转成小写
        for old, new in [
            ('PENDING', 'pending'),
            ('GRADED', 'graded'),
            ('APPROVED', 'approved'),
            ('REJECTED', 'rejected'),
        ]:
            result = await conn.execute(text(
                f"UPDATE submissions SET status = '{new}' WHERE status = '{old}'"
            ))
            print(f"  {old} -> {new}: {result.rowcount} 行")

        # 改回 ENUM 类型
        await conn.execute(text(
            "ALTER TABLE submissions MODIFY COLUMN status "
            "ENUM('pending','graded','approved','rejected') DEFAULT 'pending'"
        ))
        print("✅ 恢复为 ENUM 类型")

    print("🎉 修复完成!")


if __name__ == "__main__":
    asyncio.run(fix_status())
