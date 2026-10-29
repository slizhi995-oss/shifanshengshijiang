"""
添加新字段的数据库迁移脚本
- User表添加is_super_admin字段
- Notice表添加show_on_login字段
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine


def add_fields():
    """添加新字段"""
    with engine.connect() as conn:
        try:
            # 添加 User表的 is_super_admin 字段
            print("添加 User.is_super_admin 字段...")
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN DEFAULT FALSE"
            ))
            conn.commit()
            print("✓ User.is_super_admin 字段添加成功")
        except Exception as e:
            print(f"✗ User.is_super_admin 添加失败: {e}")
        
        try:
            # 添加 Notice表的 show_on_login 字段
            print("\n添加 Notice.show_on_login 字段...")
            conn.execute(text(
                "ALTER TABLE notices ADD COLUMN IF NOT EXISTS show_on_login BOOLEAN DEFAULT FALSE"
            ))
            conn.commit()
            print("✓ Notice.show_on_login 字段添加成功")
        except Exception as e:
            print(f"✗ Notice.show_on_login 添加失败: {e}")
    
    print("\n✅ 数据库字段添加完成！")


if __name__ == "__main__":
    add_fields()
