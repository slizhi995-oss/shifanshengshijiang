"""
Async database connection and session management.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text, inspect
from urllib.parse import urlparse

from app.core.config import settings
from app.models.base import Base


async def ensure_database_exists() -> None:
    """Ensure the database exists, create if not."""
    # 检查是否是SQLite
    if settings.DATABASE_URL.startswith('sqlite'):
        print("✅ 使用SQLite数据库，文件将自动创建")
        return
    
    # 对于MySQL/PostgreSQL等数据库
    # Parse the database URL to get connection info
    parsed = urlparse(settings.DATABASE_URL)
    db_name = parsed.path.lstrip('/')
    
    # Create a connection URL without the database name
    base_url = settings.DATABASE_URL.rsplit('/', 1)[0]
    
    # Connect to MySQL server (without specific database)
    temp_engine = create_async_engine(base_url, echo=False)
    
    try:
        async with temp_engine.connect() as conn:
            # Check if database exists
            result = await conn.execute(
                text(f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{db_name}'")
            )
            exists = result.fetchone() is not None
            
            if not exists:
                print(f"🔧 数据库 '{db_name}' 不存在，正在创建...")
                await conn.execute(text(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                await conn.commit()
                print(f"✅ 数据库 '{db_name}' 创建成功")
            else:
                print(f"✅ 数据库 '{db_name}' 已存在")
    finally:
        await temp_engine.dispose()


# Create async engine (will be initialized after database check)
engine_kwargs = {
    "echo": settings.DATABASE_ECHO,
    "pool_pre_ping": True,
}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": 10,
            "max_overflow": 20,
        }
    )

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.
    Usage in FastAPI endpoints:
        async def endpoint(db: AsyncSession = Depends(get_db)):
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_tables_exist() -> bool:
    """Check if database tables exist."""
    async with engine.connect() as conn:
        def check_tables(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            return "users" in tables
        
        return await conn.run_sync(check_tables)


async def run_migrations() -> None:
    """Run schema migrations to add missing columns."""
    is_sqlite = settings.DATABASE_URL.startswith('sqlite')
    
    # SQLite和MySQL的迁移SQL不同
    if is_sqlite:
        migrations = [
            # (table, column, sql) - SQLite版本
            ("trial_video_comments", "parent_id", "ALTER TABLE trial_video_comments ADD COLUMN parent_id INTEGER REFERENCES trial_video_comments(id)"),
            ("trial_video_comments", "is_deleted", "ALTER TABLE trial_video_comments ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"),
            ("notices", "attachment_path", "ALTER TABLE notices ADD COLUMN attachment_path VARCHAR(512) DEFAULT NULL"),
            ("notices", "display_type", "ALTER TABLE notices ADD COLUMN display_type VARCHAR(20) DEFAULT 'dialog'"),
            ("users", "is_super_admin", "ALTER TABLE users ADD COLUMN is_super_admin INTEGER DEFAULT 0"),
            ("notices", "show_on_login", "ALTER TABLE notices ADD COLUMN show_on_login INTEGER DEFAULT 0"),
            ("messages", "semester_id", "ALTER TABLE messages ADD COLUMN semester_id INTEGER"),
            ("submissions", "lesson_plan_analysis", "ALTER TABLE submissions ADD COLUMN lesson_plan_analysis TEXT DEFAULT NULL"),
            ("submissions", "video_analysis", "ALTER TABLE submissions ADD COLUMN video_analysis TEXT DEFAULT NULL"),
            ("submissions", "ai_suggested_feedback", "ALTER TABLE submissions ADD COLUMN ai_suggested_feedback TEXT DEFAULT NULL"),
            ("submissions", "ai_suggested_score", "ALTER TABLE submissions ADD COLUMN ai_suggested_score FLOAT DEFAULT NULL"),
            ("ai_model_configs", "monthly_quota", "ALTER TABLE ai_model_configs ADD COLUMN monthly_quota INTEGER DEFAULT NULL"),
        ]
        
        async with engine.begin() as conn:
            for table, column, sql in migrations:
                # SQLite: 检查列是否存在
                try:
                    result = await conn.execute(text(f"PRAGMA table_info({table})"))
                    columns = [row[1] for row in result.fetchall()]
                    
                    if column not in columns:
                        await conn.execute(text(sql))
                        print(f"✅ 已添加列 {table}.{column}")
                except Exception as e:
                    # 列可能已存在或其他错误
                    pass
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_trial_video_comments_parent_id ON trial_video_comments (parent_id)"))
    else:
        # MySQL版本
        migrations = [
            ("trial_video_comments", "parent_id", "ALTER TABLE trial_video_comments ADD COLUMN parent_id INTEGER NULL, ADD INDEX ix_trial_video_comments_parent_id (parent_id), ADD FOREIGN KEY (parent_id) REFERENCES trial_video_comments(id)"),
            ("trial_video_comments", "is_deleted", "ALTER TABLE trial_video_comments ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"),
            ("notices", "attachment_path", "ALTER TABLE notices ADD COLUMN attachment_path VARCHAR(512) DEFAULT NULL"),
            ("notices", "display_type", "ALTER TABLE notices ADD COLUMN display_type VARCHAR(20) DEFAULT 'dialog'"),
            ("users", "is_super_admin", "ALTER TABLE users ADD COLUMN is_super_admin TINYINT(1) DEFAULT 0 COMMENT '是否为超级管理员'"),
            ("notices", "show_on_login", "ALTER TABLE notices ADD COLUMN show_on_login TINYINT(1) DEFAULT 0 COMMENT '是否在登录页展示'"),
            ("messages", "semester_id", "ALTER TABLE messages ADD COLUMN semester_id INTEGER"),
            ("submissions", "lesson_plan_analysis", "ALTER TABLE submissions ADD COLUMN lesson_plan_analysis TEXT DEFAULT NULL"),
            ("submissions", "video_analysis", "ALTER TABLE submissions ADD COLUMN video_analysis TEXT DEFAULT NULL"),
            ("submissions", "ai_suggested_feedback", "ALTER TABLE submissions ADD COLUMN ai_suggested_feedback TEXT DEFAULT NULL"),
            ("submissions", "ai_suggested_score", "ALTER TABLE submissions ADD COLUMN ai_suggested_score FLOAT DEFAULT NULL"),
            ("ai_model_configs", "monthly_quota", "ALTER TABLE ai_model_configs ADD COLUMN monthly_quota INT DEFAULT NULL COMMENT '月度Token额度'"),
        ]
        
        async with engine.begin() as conn:
            for table, column, sql in migrations:
                # MySQL: 检查列是否存在
                result = await conn.execute(text(f"""
                    SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = '{table}' 
                    AND column_name = '{column}'
                """))
                exists = result.scalar()
                
                if not exists:
                    try:
                        await conn.execute(text(sql))
                        print(f"✅ 已添加列 {table}.{column}")
                    except Exception as e:
                        print(f"⚠️ 添加列 {table}.{column} 失败: {e}")


async def init_db() -> None:
    """
    Initialize database - create database and tables if they don't exist.
    Returns True if database was newly initialized.
    """
    # Step 1: Ensure database exists
    await ensure_database_exists()
    
    # Step 2: Check if tables exist
    tables_exist = await check_tables_exist()
    
    if not tables_exist:
        print("🔧 数据库表不存在，正在初始化...")
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ 数据库表创建成功")
        
        # Seed default admin user
        await seed_default_admin()
        # Seed default teacher/student accounts (三端统一默认账号)
        await seed_default_teacher_and_student()
        
        # Seed AI model configs from .env
        await seed_ai_model_configs()
        
        # Seed default resources
        await seed_default_resources()
        
        # Seed demo data (instructors, students, semesters, groups, tasks)
        await seed_demo_data()
        
        # Seed rich demo data (submissions/notices/messages/notifications/...)
        from app.core.seed_rich import seed_rich_demo_data
        await seed_rich_demo_data()
        
        return True
    else:
        print("✅ 数据表已存在，正常启动")
        # Create any new tables that don't exist yet
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Run migrations to add any missing columns
        await run_migrations()
        
        # 确保三端默认账号存在且 is_default_password=False（幂等）
        await seed_default_admin()
        await seed_default_teacher_and_student()
        
        # Seed AI model configs if table is empty
        await seed_ai_model_configs()
        
        # Seed default resources if table is empty
        await seed_default_resources()
        
        # Seed demo data if not exists
        await seed_demo_data()
        
        # Seed rich demo data if submissions empty (幂等)
        from app.core.seed_rich import seed_rich_demo_data
        await seed_rich_demo_data()
        
        return False


async def seed_default_admin() -> None:
    """Seed default admin user if not exists."""
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    
    async with async_session_factory() as session:
        # Check if admin exists
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.user_code == "admin")
        )
        existing_admin = result.scalar_one_or_none()
        
        if not existing_admin:
            admin = User(
                user_code="admin",
                name="系统管理员",
                role=UserRole.ADMIN,
                password_hash=hash_password("admin123"),
                is_default_password=False,  # 常驻默认账号，不强制首次改密
                is_super_admin=True,  # 设置为超级管理员
            )
            session.add(admin)
            await session.commit()
            print("✅ 默认超级管理员账号已创建 (admin / admin123)")
        else:
            # 如果管理员存在但不是超级管理员，则升级为超级管理员；
            # 并确保常驻默认账号不会被强制首次改密
            changed = False
            if not existing_admin.is_super_admin:
                existing_admin.is_super_admin = True
                changed = True
            if existing_admin.is_default_password:
                existing_admin.is_default_password = False
                changed = True
            if changed:
                await session.commit()
                print("✅ 默认超级管理员 (admin) 标志位已修正")
            else:
                print("ℹ️  管理员账号已存在")


async def seed_default_teacher_and_student() -> None:
    """
    Seed two常驻默认账号 for teacher and student ends, idempotent.
      - teacher / teacher123  (INSTRUCTOR)
      - student / student123  (STUDENT)
    数据库丢失重建时会自动重新创建；已存在则只修正 is_default_password=False。
    """
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    from sqlalchemy import select

    defaults = [
        {
            "user_code": "teacher",
            "password": "teacher123",
            "name": "默认教师",
            "role": UserRole.INSTRUCTOR,
            "college": "示例学院",
        },
        {
            "user_code": "student",
            "password": "student123",
            "name": "默认学生",
            "role": UserRole.STUDENT,
            "college": "示例学院",
        },
    ]

    async with async_session_factory() as session:
        any_change = False
        for d in defaults:
            result = await session.execute(
                select(User).where(User.user_code == d["user_code"])
            )
            existing = result.scalar_one_or_none()

            if not existing:
                session.add(User(
                    user_code=d["user_code"],
                    name=d["name"],
                    role=d["role"],
                    college=d["college"],
                    password_hash=hash_password(d["password"]),
                    is_default_password=False,
                    is_active=True,
                ))
                any_change = True
                print(f"✅ 默认账号已创建 ({d['user_code']} / {d['password']})")
            else:
                if existing.is_default_password:
                    existing.is_default_password = False
                    any_change = True
                    print(f"✅ 已修正 {d['user_code']} 的 is_default_password=False")
                if not existing.is_active:
                    existing.is_active = True
                    any_change = True
                    print(f"✅ 已启用 {d['user_code']} 账号")
        if any_change:
            await session.commit()


async def seed_ai_model_configs() -> None:
    """
    首次启动时将 .env 中的 AI 模型配置写入数据库。
    如果 ai_model_configs 表已有数据则跳过，保证前端修改后的配置不会被覆盖。
    """
    from app.models.ai_config import AIModelConfig

    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM ai_model_configs")
        )
        count = result.scalar()

        if count and count > 0:
            print("ℹ️  AI 模型配置表已有数据，跳过 env 初始化")
            return

        print("🔧 AI 模型配置表为空，从 .env 写入默认配置...")

        # ---------- 通义千问文本模型 ----------
        if settings.DASHSCOPE_API_KEY:
            session.add(AIModelConfig(
                name="通义千问 " + settings.DASHSCOPE_MODEL,
                provider="dashscope",
                model_id=settings.DASHSCOPE_MODEL,
                api_key=settings.DASHSCOPE_API_KEY,
                api_base_url=settings.DASHSCOPE_BASE_URL,
                model_type="text",
                is_enabled=True,
                is_default=True,
                priority=10,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                price_per_1k_tokens=0.004,
                description="文本模型 - 教案分析、生成评语、AI对话",
            ))

            # ---------- 音频模型 ----------
            session.add(AIModelConfig(
                name="通义千问 " + settings.DASHSCOPE_AUDIO_MODEL,
                provider="dashscope",
                model_id=settings.DASHSCOPE_AUDIO_MODEL,
                api_key=settings.DASHSCOPE_API_KEY,
                api_base_url=settings.DASHSCOPE_BASE_URL,
                model_type="audio",
                is_enabled=True,
                is_default=True,
                priority=10,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                price_per_1k_tokens=0.01,
                description="音频模型 - 视频语音转文字、语速分析",
            ))

            # ---------- 视觉模型 ----------
            session.add(AIModelConfig(
                name="通义千问 " + settings.DASHSCOPE_VISION_MODEL,
                provider="dashscope",
                model_id=settings.DASHSCOPE_VISION_MODEL,
                api_key=settings.DASHSCOPE_API_KEY,
                api_base_url=settings.DASHSCOPE_BASE_URL,
                model_type="vision",
                is_enabled=True,
                is_default=True,
                priority=10,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                price_per_1k_tokens=0.02,
                description="视觉模型 - 肢体语言、表情、教具使用分析",
            ))

            print("✅ 已写入通义千问 3 个模型配置（文本/音频/视觉）")

        # ---------- OpenAI ----------
        if settings.OPENAI_API_KEY:
            session.add(AIModelConfig(
                name="OpenAI " + settings.OPENAI_MODEL,
                provider="openai",
                model_id=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                api_base_url=settings.OPENAI_BASE_URL,
                model_type="text",
                is_enabled=True,
                is_default=False,
                priority=20,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                price_per_1k_tokens=0.01,
                description="OpenAI 文本模型",
            ))
            print("✅ 已写入 OpenAI 模型配置")

        # ---------- DeepSeek ----------
        if settings.DEEPSEEK_API_KEY:
            session.add(AIModelConfig(
                name="DeepSeek " + settings.DEEPSEEK_MODEL,
                provider="deepseek",
                model_id=settings.DEEPSEEK_MODEL,
                api_key=settings.DEEPSEEK_API_KEY,
                api_base_url=settings.DEEPSEEK_BASE_URL,
                model_type="text",
                is_enabled=True,
                is_default=False,
                priority=30,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
                price_per_1k_tokens=0.001,
                description="DeepSeek 文本模型",
            ))
            print("✅ 已写入 DeepSeek 模型配置")

        await session.commit()
        print("🎉 AI 模型配置初始化完成")


async def seed_default_resources() -> None:
    """Seed default educational resources if table is empty."""
    import json as _json
    from app.models.resource import Resource, ResourceCategory

    def _t(lst):
        return _json.dumps(lst, ensure_ascii=False)

    async with async_session_factory() as session:
        try:
            result = await session.execute(text("SELECT COUNT(*) FROM resources"))
            count = result.scalar()
            if count and count > 0:
                return
        except Exception:
            return

        print("Writing default educational resources...")

        resources_data = [
            # ==================== 教学视频 ====================
            dict(
                title="名师课堂：小学语文《草原》教学实录",
                description="全国特级教师执教，展示如何通过朗读指导让学生感受草原之美，课堂互动丰富，值得反复观摩学习。",
                category=ResourceCategory.VIDEO,
                url="https://www.bilibili.com/video/BV1xW411n7UC",
                tags=_t(["语文", "小学", "朗读指导", "名师课堂"]),
                subject="语文", grade_level="小学", source="B站-名师课堂",
                is_featured=True, sort_order=100,
                cover_image="https://picsum.photos/seed/caoyuan/480/270",
            ),
            dict(
                title="数学微课：初中函数概念引入",
                description="通过生活实例引入函数概念，层层递进，帮助学生建立函数思维。适合师范生学习如何将抽象概念具象化。",
                category=ResourceCategory.VIDEO,
                url="https://www.bilibili.com/video/BV1GJ411x7io",
                tags=_t(["数学", "初中", "概念教学", "微课"]),
                subject="数学", grade_level="初中", source="B站-数学教学",
                sort_order=95,
                cover_image="https://picsum.photos/seed/mathfunc/480/270",
            ),
            dict(
                title="英语教学：情境创设与口语训练",
                description="展示如何在英语课堂中创设真实语言情境，激发学生英语交流的兴趣和自信。包含TPR教学法、角色扮演等实用策略。",
                category=ResourceCategory.VIDEO,
                url="https://www.bilibili.com/video/BV1bK4y1C7NE",
                tags=_t(["英语", "口语", "情境教学", "TPR"]),
                subject="英语", grade_level="初中", source="B站-英语教学",
                sort_order=90,
                cover_image="https://picsum.photos/seed/english1/480/270",
            ),
            dict(
                title="课堂管理技巧：新手教师必看",
                description="资深教师分享课堂管理的10个实用技巧，包括注意力集中策略、纪律管理方法、时间分配原则以及突发情况应对。",
                category=ResourceCategory.VIDEO,
                url="https://www.bilibili.com/video/BV1sT4y1G7SN",
                tags=_t(["课堂管理", "教学技巧", "新手教师"]),
                subject="通用", grade_level="通用", source="B站-教师成长",
                is_featured=True, sort_order=98,
                cover_image="https://picsum.photos/seed/classroom1/480/270",
            ),
            dict(
                title="板书设计的艺术与实践",
                description="系统讲解板书设计的原则、方法和创意技巧，配合大量优秀板书案例分析。涵盖提纲式、图表式、网络式等多种板书形式。",
                category=ResourceCategory.VIDEO,
                url="https://www.bilibili.com/video/BV1x54y1n7tB",
                tags=_t(["板书设计", "教学技能", "基本功"]),
                subject="通用", grade_level="通用", source="B站-教学技能",
                sort_order=85,
                cover_image="https://picsum.photos/seed/blackboard/480/270",
            ),

            # ==================== 观摩课程 ====================
            dict(
                title="2024年全国小学数学优质课一等奖",
                description="全国小学数学优质课竞赛一等奖获奖课程完整视频，展现高水平数学课堂教学，课堂结构完整、互动充分。",
                category=ResourceCategory.OBSERVATION,
                url="https://www.bilibili.com/video/BV1kC4y1N7Tx",
                tags=_t(["数学", "小学", "优质课", "获奖课例"]),
                subject="数学", grade_level="小学", source="全国教学竞赛",
                is_featured=True, sort_order=100,
                cover_image="https://picsum.photos/seed/mathclass/480/270",
            ),
            dict(
                title="省级教学能手展示课：高中物理实验探究",
                description="省级教学能手展示课，以实验驱动物理概念教学，引导学生自主提出假设、设计实验、分析数据。",
                category=ResourceCategory.OBSERVATION,
                url="https://www.bilibili.com/video/BV1mK4y1V7nC",
                tags=_t(["物理", "高中", "实验教学", "探究式教学"]),
                subject="物理", grade_level="高中", source="省级教学展示",
                sort_order=90,
                cover_image="https://picsum.photos/seed/physics1/480/270",
            ),
            dict(
                title="初中语文公开课：《背影》课堂实录",
                description="市级公开课，教师引导学生通过细读文本感受父爱主题，课堂设计体现以学生为中心的教学理念。",
                category=ResourceCategory.OBSERVATION,
                url="https://www.bilibili.com/video/BV1uT4y1E7kx",
                tags=_t(["语文", "初中", "散文教学", "公开课"]),
                subject="语文", grade_level="初中", source="市级公开课",
                sort_order=85,
                cover_image="https://picsum.photos/seed/chinese1/480/270",
            ),
            dict(
                title="高中化学示范课：氧化还原反应",
                description="区级示范课完整录像，运用实验演示与动画模拟相结合的方式，帮助学生理解电子转移的微观本质。",
                category=ResourceCategory.OBSERVATION,
                url="https://www.bilibili.com/video/BV1Pp4y1r7Wx",
                tags=_t(["化学", "高中", "氧化还原", "示范课"]),
                subject="化学", grade_level="高中", source="区级示范课",
                sort_order=80,
                cover_image="https://picsum.photos/seed/chemistry1/480/270",
            ),

            # ==================== 资源网站 ====================
            dict(
                title="国家中小学智慧教育平台",
                description="教育部官方平台，提供海量优质课程资源、教学设计、教材解读等，涵盖各学科各学段，是师范生备课的首选资源库。",
                category=ResourceCategory.WEBSITE,
                url="https://www.zxx.edu.cn/",
                tags=_t(["官方平台", "课程资源", "教学设计"]),
                subject="通用", grade_level="通用", source="教育部",
                is_featured=True, sort_order=100,
                cover_image="https://picsum.photos/seed/smartedu/480/270",
            ),
            dict(
                title="中国知网 - 教育论文库",
                description="查阅教育教学相关学术论文，了解最新教育研究成果与教学改革动态。可检索学科教学法、课程设计等领域的核心文献。",
                category=ResourceCategory.WEBSITE,
                url="https://www.cnki.net/",
                tags=_t(["学术论文", "教育研究", "知网"]),
                subject="通用", grade_level="通用", source="CNKI",
                sort_order=90,
                cover_image="https://picsum.photos/seed/cnki2024/480/270",
            ),
            dict(
                title="学科网 - 教学资源下载",
                description="提供各学科各学段教案、课件、试卷等教学资源下载，辅助备课和教学设计。资源按教材版本分类，检索便捷。",
                category=ResourceCategory.WEBSITE,
                url="https://www.zxxk.com/",
                tags=_t(["教案", "课件", "试卷", "教学资源"]),
                subject="通用", grade_level="通用", source="学科网",
                sort_order=85,
                cover_image="https://picsum.photos/seed/xueke88/480/270",
            ),
            dict(
                title="中国大学MOOC",
                description="国家精品在线课程平台，可选修教育学、心理学、学科教学法等师范类课程，获取权威学习证书。",
                category=ResourceCategory.WEBSITE,
                url="https://www.icourse163.org/",
                tags=_t(["在线课程", "MOOC", "教育学"]),
                subject="通用", grade_level="大学", source="中国大学MOOC",
                sort_order=80,
                cover_image="https://picsum.photos/seed/mooc2024/480/270",
            ),
            dict(
                title="人民教育出版社官网",
                description="提供人教版各学科教材的电子版、教师用书、配套资源及课标解读，帮助师范生准确把握教材内容。",
                category=ResourceCategory.WEBSITE,
                url="https://www.pep.com.cn/",
                tags=_t(["人教版", "教材", "课标", "教师用书"]),
                subject="通用", grade_level="通用", source="人民教育出版社",
                is_featured=True, sort_order=95,
                cover_image="https://picsum.photos/seed/pep2024/480/270",
            ),

            # ==================== 优秀选题 ====================
            dict(
                title="小学语文：部编版二年级《四季》诗歌教学设计",
                description="以儿童诗《四季》为载体，通过朗读、仿写、表演等多元方式感受四季之美，培养学生语言表达能力。适合低年级试讲选题。",
                category=ResourceCategory.TOPIC,
                tags=_t(["语文", "小学", "诗歌教学", "低年级"]),
                subject="语文", grade_level="小学低年级", source="往届优秀选题",
                is_featured=True, sort_order=100,
                cover_image="https://picsum.photos/seed/siji2024/480/270",
                content='''<h3>一、选题背景</h3>
<p>《四季》是部编版小学语文一年级上册的一篇儿童诗，以简洁明快的语言描绘了春夏秋冬四个季节的典型景物。本课适合师范生试讲，可充分展示朗读指导能力和课堂互动设计能力。</p>

<h3>二、选题亮点</h3>
<ul>
<li>以朗读为主线，通过个人读、齐读、分角色读等多种方式让学生感受诗歌韵律与节奏</li>
<li>设计仿写环节，引导学生观察身边事物并创编属于自己的四季小诗</li>
<li>融合艺术元素，让学生用简笔画表达对四季的理解，实现跨学科整合</li>
<li>课堂环节清晰，导入、新授、练习、拓展层层推进，适合10-15分钟试讲展示</li>
</ul>

<h3>三、教学目标</h3>
<ul>
<li>正确、流利、有感情地朗读课文，背诵课文</li>
<li>理解课文内容，知道四季的特征，感受四季之美</li>
<li>能仿照课文，用一两句话描述自己喜欢的季节</li>
</ul>

<h3>四、推荐教学流程</h3>
<table>
<tr><th>环节</th><th>时长</th><th>活动</th></tr>
<tr><td>情境导入</td><td>2分钟</td><td>展示四季图片，引导学生说一说最喜欢的季节</td></tr>
<tr><td>初读感知</td><td>3分钟</td><td>教师范读，学生跟读，正音正字</td></tr>
<tr><td>精读品味</td><td>4分钟</td><td>逐节赏读，体会关键词语，指导朗读语气</td></tr>
<tr><td>拓展仿写</td><td>3分钟</td><td>出示句式支架，学生仿写一节小诗并展示</td></tr>
<tr><td>总结提升</td><td>1分钟</td><td>配乐朗读全诗，总结四季特点</td></tr>
</table>

<h3>五、评委关注点</h3>
<p>朗读指导是否有层次感；板书设计是否美观清晰；课堂语言是否亲切自然、符合低年级学生特点。</p>''',
            ),
            dict(
                title="初中数学：人教版八年级《一元二次方程应用题》教学设计",
                description="从实际问题出发，建立一元二次方程模型，培养学生数学建模能力。涵盖面积问题、利润问题等经典类型。",
                category=ResourceCategory.TOPIC,
                tags=_t(["数学", "初中", "方程", "应用题", "数学建模"]),
                subject="数学", grade_level="初中", source="往届优秀选题",
                is_featured=True, sort_order=95,
                cover_image="https://picsum.photos/seed/mathapp1/480/270",
                content='''<h3>一、选题背景</h3>
<p>一元二次方程应用题是初中数学的重要内容，涉及面积变化、利润计算、增长率等实际问题。本课重点考察师范生将生活问题抽象为数学模型的教学能力。</p>

<h3>二、选题亮点</h3>
<ul>
<li>从真实生活情境引入（如校园花坛改造），激发学生学习兴趣</li>
<li>分层设计问题，照顾不同水平学生：基础型、提高型、拓展型</li>
<li>强调"审题-建模-求解-检验"完整建模过程，培养核心素养</li>
<li>设计小组合作探究环节，体现以学生为中心的教学理念</li>
</ul>

<h3>三、教学目标</h3>
<ul>
<li>能根据实际问题中的数量关系列出一元二次方程</li>
<li>掌握面积类、增长率类应用题的建模方法</li>
<li>养成检验解的合理性的习惯，理解数学解与实际解的区别</li>
</ul>

<h3>四、推荐教学流程</h3>
<table>
<tr><th>环节</th><th>时长</th><th>活动</th></tr>
<tr><td>情境导入</td><td>2分钟</td><td>展示校园花坛扩建方案，引出面积变化问题</td></tr>
<tr><td>合作探究</td><td>4分钟</td><td>学生分组讨论，尝试列方程并求解</td></tr>
<tr><td>方法总结</td><td>3分钟</td><td>归纳建模步骤，板书关键方法</td></tr>
<tr><td>分层练习</td><td>3分钟</td><td>基础题全班做，拓展题小组挑战</td></tr>
<tr><td>总结反思</td><td>1分钟</td><td>学生分享收获，教师点评总结</td></tr>
</table>

<h3>五、易犯错误提醒</h3>
<p>试讲时注意：设元要明确单位和含义；列方程后必须检验根的合理性（如长度不能为负）；板书要体现完整的解题步骤。</p>''',
            ),
            dict(
                title="高中英语：人教版必修二 Reading and Thinking 读写整合课",
                description="以新课标为指导，采用读写整合模式，通过阅读输入促进写作输出，提升学生英语综合语言运用能力。",
                category=ResourceCategory.TOPIC,
                tags=_t(["英语", "高中", "读写整合", "核心素养"]),
                subject="英语", grade_level="高中", source="往届优秀选题",
                sort_order=88,
                cover_image="https://picsum.photos/seed/engread1/480/270",
                content='''<h3>一、选题背景</h3>
<p>新课标强调英语学科核心素养包括语言能力、文化意识、思维品质和学习能力四个维度。Reading and Thinking板块将阅读与思维训练有机结合，是展示师范生教学设计能力的理想选题。</p>

<h3>二、选题亮点</h3>
<ul>
<li>遵循新课标"学习理解-应用实践-迁移创新"三层活动设计框架</li>
<li>读写一体化设计，以读促写、以写深读，形成完整的语言学习闭环</li>
<li>注重高阶思维培养：分析、评价、创造层次的问题设计</li>
<li>全英文授课展示语言能力，指令清晰、过渡自然</li>
</ul>

<h3>三、教学目标</h3>
<ul>
<li>学生能理解文章主旨大意，提取关键信息并完成阅读任务</li>
<li>学生能运用文中目标语言结构进行书面表达</li>
<li>学生能对文章主题形成自己的观点并进行简短论述</li>
</ul>

<h3>四、推荐教学流程</h3>
<table>
<tr><th>环节</th><th>时长</th><th>活动</th></tr>
<tr><td>Lead-in</td><td>2min</td><td>图片/视频导入，激活背景知识，引出话题</td></tr>
<tr><td>Pre-reading</td><td>1min</td><td>预测环节，根据标题和图片预测文章内容</td></tr>
<tr><td>While-reading</td><td>5min</td><td>略读获取主旨 + 细读完成信息提取任务</td></tr>
<tr><td>Post-reading</td><td>3min</td><td>运用目标语言进行口头或书面输出</td></tr>
<tr><td>Summary</td><td>1min</td><td>总结本课重点，布置课后延伸任务</td></tr>
</table>''',
            ),
            dict(
                title="小学科学：教科版四年级《声音的产生》探究课",
                description="以实验探究为核心，引导学生通过观察、实验、讨论等方式自主发现声音产生的原理，培养科学思维。",
                category=ResourceCategory.TOPIC,
                tags=_t(["科学", "小学", "实验探究", "声音"]),
                subject="科学", grade_level="小学", source="往届优秀选题",
                sort_order=82,
                cover_image="https://picsum.photos/seed/sound123/480/270",
                content='''<h3>一、选题背景</h3>
<p>《声音的产生》是教科版四年级上册科学的经典内容。本课以实验探究为核心活动形式，能充分展示师范生的实验操作指导能力和科学探究教学设计能力。</p>

<h3>二、选题亮点</h3>
<ul>
<li>准备丰富的实验器材（钢尺、鼓、音叉、橡皮筋等），增强学生动手操作机会</li>
<li>采用"提出问题-作出假设-实验验证-得出结论"的科学探究流程</li>
<li>设计对比实验，帮助学生理解"振动"是声音产生的根本原因</li>
<li>联系生活实际，引导学生解释日常声音现象</li>
</ul>

<h3>三、教学目标</h3>
<ul>
<li>知道声音是由物体振动产生的</li>
<li>能通过实验观察归纳声音产生的条件</li>
<li>体验科学探究的基本过程，培养观察和表达能力</li>
</ul>

<h3>四、实验设计建议</h3>
<table>
<tr><th>实验</th><th>器材</th><th>观察要点</th></tr>
<tr><td>钢尺振动发声</td><td>钢尺、桌面</td><td>拨动钢尺观察振动与声音的关系</td></tr>
<tr><td>鼓面跳动</td><td>小鼓、碎纸屑</td><td>敲鼓时纸屑跳动，停止敲击后纸屑静止</td></tr>
<tr><td>音叉触水</td><td>音叉、水槽</td><td>振动的音叉接触水面产生水花</td></tr>
<tr><td>喉部感受</td><td>无</td><td>手摸喉部，发声时感受声带振动</td></tr>
</table>''',
            ),
            dict(
                title="初中历史：部编版七年级《秦统一中国》教学设计",
                description="以秦始皇统一六国为主线，引导学生理解统一的历史意义，培养历史时空观念和史料实证意识。",
                category=ResourceCategory.TOPIC,
                tags=_t(["历史", "初中", "秦朝", "统一"]),
                subject="历史", grade_level="初中", source="往届优秀选题",
                sort_order=78,
                cover_image="https://picsum.photos/seed/qinuni1/480/270",
                content='''<h3>一、选题背景</h3>
<p>《秦统一中国》是部编版七年级上册的重要课节，内容涉及统一战争、中央集权制度建立、统一措施等。本课信息量大，适合考察师范生驾驭复杂知识的能力。</p>

<h3>二、选题亮点</h3>
<ul>
<li>以时间轴梳理统一进程，培养学生历史时空观念</li>
<li>引入地图、文物图片等史料，体现史料实证素养</li>
<li>设计角色扮演活动，让学生站在秦始皇视角思考统一措施的必要性</li>
<li>引导学生辩证评价秦始皇的历史功过</li>
</ul>

<h3>三、推荐教学流程</h3>
<table>
<tr><th>环节</th><th>时长</th><th>活动</th></tr>
<tr><td>导入</td><td>2分钟</td><td>展示秦始皇陵兵马俑图片，引出课题</td></tr>
<tr><td>统一过程</td><td>3分钟</td><td>结合地图讲解灭六国顺序和统一策略</td></tr>
<tr><td>巩固措施</td><td>4分钟</td><td>分组讨论政治、经济、文化、军事统一措施</td></tr>
<tr><td>评价讨论</td><td>2分钟</td><td>辩证评价秦始皇：功与过</td></tr>
<tr><td>总结</td><td>1分钟</td><td>板书总结，强调统一的历史意义</td></tr>
</table>''',
            ),

            # ==================== 教学文档 ====================
            dict(
                title="师范生试讲评分标准详解",
                description="详细解读各学科试讲评分标准，包括教学目标、教学过程、教态仪表、板书设计等维度的评分要点和常见扣分项。",
                category=ResourceCategory.DOCUMENT,
                tags=_t(["评分标准", "试讲准备", "教学规范"]),
                subject="通用", grade_level="通用", source="教务处",
                is_featured=True, sort_order=100,
                cover_image="https://picsum.photos/seed/score001/480/270",
                content='''<h3>一、评分维度与权重</h3>
<table>
<tr><th>评分维度</th><th>分值</th><th>主要考察内容</th></tr>
<tr><td>教学目标</td><td>10分</td><td>目标是否明确、具体、可操作，是否符合课标要求</td></tr>
<tr><td>教学内容</td><td>20分</td><td>内容把握是否准确，重难点是否突出，知识体系是否完整</td></tr>
<tr><td>教学过程</td><td>30分</td><td>环节设计是否合理，过渡是否自然，时间分配是否得当</td></tr>
<tr><td>教学方法</td><td>15分</td><td>方法选择是否恰当，是否体现启发式、探究式教学</td></tr>
<tr><td>教态仪表</td><td>10分</td><td>语言表达、肢体语言、精神面貌、着装规范</td></tr>
<tr><td>板书设计</td><td>10分</td><td>板书是否简洁美观、逻辑清晰、书写规范</td></tr>
<tr><td>创新亮点</td><td>5分</td><td>是否有教学创新、信息技术融合、个人特色</td></tr>
</table>

<h3>二、常见扣分项</h3>
<ul>
<li>教学目标空泛，使用"了解""掌握"等模糊词汇却无具体行为动词</li>
<li>时间分配不当：导入过长(超过3分钟)或结尾草率</li>
<li>板书杂乱无章，字迹潦草，或全程无板书</li>
<li>缺乏互动设计，全程自说自话，没有提问和预设学生回答</li>
<li>教态不自然：眼神回避、小动作多、语速过快或过慢</li>
<li>脱离教材和课标，内容深度或广度不符合学段要求</li>
</ul>

<h3>三、高分技巧</h3>
<ul>
<li>导入要新颖：可用故事、问题、实验、视频等方式，避免直接"翻开课本第X页"</li>
<li>过渡要自然：用承上启下的语言连接各教学环节</li>
<li>提问有层次：从回忆性问题到分析性问题再到评价性问题</li>
<li>板书提前设计：试讲前在纸上画好板书草图</li>
<li>结尾有升华：总结回顾要点，适当拓展延伸，布置有思考性的作业</li>
</ul>''',
            ),
            dict(
                title="教案撰写规范与模板",
                description="提供标准教案格式模板及撰写要点说明，帮助师范生规范教案撰写，包括教学目标的行为动词使用、教学过程的详略安排等。",
                category=ResourceCategory.DOCUMENT,
                tags=_t(["教案模板", "教案规范", "备课"]),
                subject="通用", grade_level="通用", source="教学资源库",
                sort_order=95,
                cover_image="https://picsum.photos/seed/jiaoan01/480/270",
                content='''<h3>一、标准教案结构</h3>
<table>
<tr><th>序号</th><th>项目</th><th>说明</th></tr>
<tr><td>1</td><td>课题名称</td><td>写明学科、年级、教材版本、章节名称</td></tr>
<tr><td>2</td><td>课型</td><td>新授课/复习课/实验课/习题课 等</td></tr>
<tr><td>3</td><td>课时</td><td>本节课在单元中的位置，第几课时</td></tr>
<tr><td>4</td><td>教学目标</td><td>从知识与技能、过程与方法、情感态度价值观三维书写（或核心素养目标）</td></tr>
<tr><td>5</td><td>教学重难点</td><td>重点：学生必须掌握的内容；难点：学生不易理解的内容</td></tr>
<tr><td>6</td><td>教学方法</td><td>讲授法、讨论法、探究法、演示法 等</td></tr>
<tr><td>7</td><td>教学准备</td><td>教具、学具、多媒体课件等</td></tr>
<tr><td>8</td><td>教学过程</td><td>详见下方说明</td></tr>
<tr><td>9</td><td>板书设计</td><td>用框图或文字展示板书布局</td></tr>
<tr><td>10</td><td>教学反思</td><td>课后填写，反思教学效果和改进方向</td></tr>
</table>

<h3>二、教学目标撰写规范</h3>
<p>推荐使用ABCD模式撰写教学目标：</p>
<ul>
<li><strong>A(Audience)</strong> - 学习者：如"学生能够..."</li>
<li><strong>B(Behavior)</strong> - 行为动词：如"说出""解释""计算""设计"</li>
<li><strong>C(Condition)</strong> - 条件：如"在小组讨论后""借助教具"</li>
<li><strong>D(Degree)</strong> - 标准：如"正确率达到80%""至少列举3个"</li>
</ul>

<h3>三、教学过程详略安排</h3>
<ul>
<li>导入环节(2-3分钟)：简明扼要，快速进入主题</li>
<li>新授环节(15-20分钟)：教案中最详细的部分，写明师生活动、预设问题、预设回答</li>
<li>练习巩固(8-10分钟)：题目要有梯度，从基础到综合</li>
<li>小结作业(3-5分钟)：总结要精炼，作业要分层</li>
</ul>''',
            ),
            dict(
                title="试讲常见问题与应对策略",
                description="总结师范生试讲中最常出现的15个问题及其改进方法，涵盖语言表达、时间控制、互动设计、板书书写等方面。",
                category=ResourceCategory.DOCUMENT,
                tags=_t(["试讲技巧", "常见问题", "教学改进"]),
                subject="通用", grade_level="通用", source="教学督导组",
                is_featured=True, sort_order=92,
                cover_image="https://picsum.photos/seed/faq2024/480/270",
                content='''<h3>一、语言表达类</h3>
<table>
<tr><th>常见问题</th><th>改进策略</th></tr>
<tr><td>语速过快，学生跟不上节奏</td><td>刻意放慢语速，关键知识点要停顿强调，可以录音回听练习</td></tr>
<tr><td>口头禅过多（"然后""那个""嗯"）</td><td>提前准备好过渡语，用短暂停顿代替口头禅</td></tr>
<tr><td>课堂语言不规范，太口语化</td><td>使用学科术语，避免"这个东西""那个什么"等模糊表述</td></tr>
<tr><td>提问方式单一，总是"对不对""是不是"</td><td>设计开放性问题："你怎么看？""能举个例子吗？""还有其他方法吗？"</td></tr>
</table>

<h3>二、教学设计类</h3>
<table>
<tr><th>常见问题</th><th>改进策略</th></tr>
<tr><td>导入时间过长，占用正课时间</td><td>导入控制在2分钟以内，与课题直接相关</td></tr>
<tr><td>环节之间缺乏衔接</td><td>提前设计过渡语，如"学完了...接下来让我们..."</td></tr>
<tr><td>缺少学生活动，全程"一言堂"</td><td>每个主要环节至少设计一个学生参与的活动</td></tr>
<tr><td>结尾仓促，没有总结提升</td><td>预留1-2分钟用于总结、作业布置和情感升华</td></tr>
</table>

<h3>三、教态与板书类</h3>
<table>
<tr><th>常见问题</th><th>改进策略</th></tr>
<tr><td>眼神只盯教案或PPT</td><td>试讲前充分熟悉内容，用目光环视全场</td></tr>
<tr><td>站姿僵硬或频繁走动</td><td>自然站立，适度移动，重点讲解时可走近"学生"</td></tr>
<tr><td>板书字迹潦草或布局混乱</td><td>提前设计板书，分主板书区和副板书区，字体大小适中</td></tr>
<tr><td>边写边讲，背对"学生"时间过长</td><td>先讲后写，或侧身书写，保持与学生的交流</td></tr>
</table>''',
            ),
            dict(
                title="新课标核心素养导向的教学设计指南",
                description="基于2022版义务教育课程方案和各学科课程标准，阐述如何在教学设计中落实核心素养目标，附多学科设计案例。",
                category=ResourceCategory.DOCUMENT,
                tags=_t(["新课标", "核心素养", "教学设计", "课程标准"]),
                subject="通用", grade_level="通用", source="课程研究中心",
                sort_order=88,
                cover_image="https://picsum.photos/seed/hexinsu1/480/270",
                content='''<h3>一、什么是核心素养导向的教学</h3>
<p>2022年版义务教育课程方案明确提出，课程实施要从"知识本位"转向"素养本位"。教学设计不再仅仅关注学生"学了什么"，更要关注学生"能做什么"和"成为怎样的人"。</p>

<h3>二、各学科核心素养概览</h3>
<table>
<tr><th>学科</th><th>核心素养</th></tr>
<tr><td>语文</td><td>语言运用、思维能力、审美创造、文化自信</td></tr>
<tr><td>数学</td><td>数学抽象、逻辑推理、数学建模、直觉想象、数据分析、数学运算</td></tr>
<tr><td>英语</td><td>语言能力、文化意识、思维品质、学习能力</td></tr>
<tr><td>物理</td><td>物理观念、科学思维、科学探究、科学态度与责任</td></tr>
<tr><td>历史</td><td>唯物史观、时空观念、史料实证、历史解释、家国情怀</td></tr>
</table>

<h3>三、教学设计转化要点</h3>
<ul>
<li><strong>目标层面</strong>：将三维目标整合为素养目标，用可观测的行为动词描述</li>
<li><strong>内容层面</strong>：选择有挑战性的真实情境和核心任务驱动学习</li>
<li><strong>过程层面</strong>：设计"学习理解-应用实践-迁移创新"层级递进的活动</li>
<li><strong>评价层面</strong>：嵌入过程性评价，关注学生在真实任务中的表现</li>
</ul>

<h3>四、试讲中如何体现核心素养</h3>
<ul>
<li>教学目标中明确写出所培养的核心素养维度</li>
<li>至少设计一个需要学生高阶思维参与的探究活动</li>
<li>在教学过程中体现对学生思维过程的关注，而非仅关注结果</li>
<li>评价设计中包含对核心素养表现的观察维度</li>
</ul>''',
            ),
        ]

        for data in resources_data:
            session.add(Resource(**data))

        await session.commit()
        print(f"Default resources seeded: {len(resources_data)} items")


async def seed_demo_data() -> None:
    """Seed demo instructors, students, semesters, groups, and tasks."""
    from app.models.user import User, UserRole
    from app.models.semester import Semester, SemesterStatus
    from app.models.group import Group
    from app.models.task import Task
    from app.core.security import hash_password
    from sqlalchemy import select
    from datetime import date, datetime

    async with async_session_factory() as session:
        # Check if demo data already exists
        # 注：不能用 INSTRUCTOR 角色判断（默认 teacher 账号也是 INSTRUCTOR），
        # 改用固定 user_code "T001" 作为 demo 数据存在标记
        result = await session.execute(
            select(User).where(User.user_code == "T001")
        )
        if result.scalars().first():
            print("ℹ️  演示数据已存在（T001 已创建），跳过")
            return

        print("🔧 正在创建演示数据（教师、学生、批次、分组、任务）...")
        pwd = hash_password("123456")

        # ==================== Instructors ====================
        instructors = [
            User(user_code="T001", name="王建华", role=UserRole.INSTRUCTOR,
                 password_hash=pwd, is_default_password=True,
                 college="教育学院", major="课程与教学论",
                 email="wangjh@edu.cn", phone="13800001001"),
            User(user_code="T002", name="李明珠", role=UserRole.INSTRUCTOR,
                 password_hash=pwd, is_default_password=True,
                 college="教育学院", major="学科教学（语文）",
                 email="limz@edu.cn", phone="13800001002"),
            User(user_code="T003", name="张国强", role=UserRole.INSTRUCTOR,
                 password_hash=pwd, is_default_password=True,
                 college="教育学院", major="学科教学（数学）",
                 email="zhanggq@edu.cn", phone="13800001003"),
        ]
        session.add_all(instructors)
        await session.flush()
        print(f"✅ 已创建 {len(instructors)} 个教师账号")

        # ==================== Students ====================
        students_data = [
            # 王建华老师的学生
            ("S2024001", "陈思远", "教育学院", "学科教学（语文）", "2022级语教1班"),
            ("S2024002", "刘雨萱", "教育学院", "学科教学（语文）", "2022级语教1班"),
            ("S2024003", "张浩然", "教育学院", "学科教学（数学）", "2022级数教1班"),
            ("S2024004", "王欣怡", "教育学院", "学科教学（数学）", "2022级数教1班"),
            ("S2024005", "赵天宇", "教育学院", "学科教学（英语）", "2022级英教1班"),
            # 李明珠老师的学生
            ("S2024006", "孙雅琪", "教育学院", "学科教学（语文）", "2022级语教2班"),
            ("S2024007", "周浩宇", "教育学院", "学科教学（语文）", "2022级语教2班"),
            ("S2024008", "吴思颖", "教育学院", "学科教学（英语）", "2022级英教1班"),
            ("S2024009", "郑凯文", "教育学院", "学科教学（英语）", "2022级英教1班"),
            ("S2024010", "马晓晨", "教育学院", "小学教育", "2022级小教1班"),
            # 张国强老师的学生
            ("S2024011", "林子涵", "教育学院", "学科教学（数学）", "2022级数教2班"),
            ("S2024012", "黄梦瑶", "教育学院", "学科教学（数学）", "2022级数教2班"),
            ("S2024013", "杨睿哲", "教育学院", "小学教育", "2022级小教1班"),
            ("S2024014", "胡欣然", "教育学院", "学科教学（物理）", "2022级物教1班"),
            ("S2024015", "罗嘉豪", "教育学院", "学科教学（物理）", "2022级物教1班"),
        ]
        students = []
        for code, name, college, major, cls in students_data:
            s = User(user_code=code, name=name, role=UserRole.STUDENT,
                     password_hash=pwd, is_default_password=True,
                     college=college, major=major, class_name=cls)
            students.append(s)
        session.add_all(students)
        await session.flush()
        print(f"✅ 已创建 {len(students)} 个学生账号")

        # ==================== Semesters ====================
        sem1 = Semester(
            name="2025年春季试讲批次",
            status=SemesterStatus.ACTIVE,
            start_date=date(2025, 3, 1),
            end_date=date(2025, 7, 15),
            description="2024-2025学年第二学期师范生教学实践，本批次重点训练课堂导入与板书设计。"
        )
        sem2 = Semester(
            name="2024年秋季试讲批次",
            status=SemesterStatus.COMPLETED,
            start_date=date(2024, 9, 1),
            end_date=date(2025, 1, 15),
            description="2024-2025学年第一学期师范生教学实践，侧重基础教学技能训练。"
        )
        session.add_all([sem1, sem2])
        await session.flush()
        print("✅ 已创建 2 个试讲批次")

        # ==================== Groups ====================
        # 王建华 -> students 0-4 (春季)
        for i in range(5):
            session.add(Group(semester_id=sem1.id, instructor_id=instructors[0].id, student_id=students[i].id))
        # 李明珠 -> students 5-9 (春季)
        for i in range(5, 10):
            session.add(Group(semester_id=sem1.id, instructor_id=instructors[1].id, student_id=students[i].id))
        # 张国强 -> students 10-14 (春季)
        for i in range(10, 15):
            session.add(Group(semester_id=sem1.id, instructor_id=instructors[2].id, student_id=students[i].id))
        # 秋季批次也分一些
        for i in range(5):
            session.add(Group(semester_id=sem2.id, instructor_id=instructors[0].id, student_id=students[i].id))
        for i in range(5, 10):
            session.add(Group(semester_id=sem2.id, instructor_id=instructors[1].id, student_id=students[i].id))
        await session.flush()
        print("✅ 已创建分组关系")

        # ==================== Tasks ====================
        tasks = [
            Task(
                title="第一次试讲：课堂导入设计与实践",
                content="""<h3>任务要求</h3>
<p>请选择一篇课文或一个知识点，设计一个5-8分钟的课堂导入环节，并录制试讲视频。</p>
<h4>具体要求：</h4>
<ol>
<li><strong>教案</strong>：撰写完整的课堂导入教案，包括教学目标、导入方式、预设问题等</li>
<li><strong>视频</strong>：录制试讲视频（5-8分钟），要求面对镜头、声音清晰</li>
<li><strong>导入方式</strong>：可选择情境导入、问题导入、故事导入、实验导入等方式</li>
</ol>
<h4>评分标准：</h4>
<ul>
<li>导入设计的创新性与吸引力（30%）</li>
<li>与教学内容的关联度（25%）</li>
<li>语言表达与教态（25%）</li>
<li>时间把控（20%）</li>
</ul>""",
                semester_id=sem1.id,
                instructor_id=instructors[0].id,
                deadline=datetime(2025, 4, 15, 23, 59, 59),
                require_lesson_plan=True,
                require_video=True,
                is_published=True,
            ),
            Task(
                title="第二次试讲：新授课完整教学设计",
                content="""<h3>任务要求</h3>
<p>请选择一个教学单元，设计一节完整的新授课（15-20分钟），并录制试讲视频。</p>
<h4>具体要求：</h4>
<ol>
<li><strong>教案</strong>：撰写完整教案，包括教学目标、重难点、教学过程、板书设计</li>
<li><strong>视频</strong>：录制完整试讲视频（15-20分钟）</li>
<li><strong>教学环节</strong>：须包含导入、新授、巩固练习、小结四个环节</li>
</ol>
<h4>评分标准：</h4>
<ul>
<li>教学目标的明确性与可达成性（20%）</li>
<li>教学过程的逻辑性与完整性（25%）</li>
<li>师生互动设计（20%）</li>
<li>语言表达、板书与教态（20%）</li>
<li>时间分配合理性（15%）</li>
</ul>""",
                semester_id=sem1.id,
                instructor_id=instructors[0].id,
                deadline=datetime(2025, 5, 30, 23, 59, 59),
                require_lesson_plan=True,
                require_video=True,
                is_published=True,
            ),
            Task(
                title="语文试讲：古诗词鉴赏教学",
                content="""<h3>任务要求</h3>
<p>请选择一首初中或高中古诗词，设计并录制一节10-15分钟的古诗词鉴赏课。</p>
<h4>具体要求：</h4>
<ol>
<li>教案中需体现"知人论世"的鉴赏方法</li>
<li>设计至少两个有深度的探究问题</li>
<li>包含朗读指导环节</li>
<li>录制试讲视频（10-15分钟）</li>
</ol>""",
                semester_id=sem1.id,
                instructor_id=instructors[1].id,
                deadline=datetime(2025, 5, 15, 23, 59, 59),
                require_lesson_plan=True,
                require_video=True,
                is_published=True,
            ),
            Task(
                title="数学试讲：概念课教学设计",
                content="""<h3>任务要求</h3>
<p>请选择一个初中或高中数学概念（如函数、向量、概率等），设计一节概念引入课并录制试讲视频。</p>
<h4>具体要求：</h4>
<ol>
<li>教案须体现"从具体到抽象"的概念建构过程</li>
<li>设计至少一个生活情境引入</li>
<li>包含概念辨析环节</li>
<li>录制试讲视频（10-15分钟）</li>
</ol>""",
                semester_id=sem1.id,
                instructor_id=instructors[2].id,
                deadline=datetime(2025, 5, 20, 23, 59, 59),
                require_lesson_plan=True,
                require_video=True,
                is_published=True,
            ),
            # 秋季批次的已完成任务
            Task(
                title="教学基本功训练：自我介绍与课堂常规",
                content="""<h3>任务要求</h3>
<p>录制一段3-5分钟的教师自我介绍视频，模拟开学第一课的场景。</p>
<ol>
<li>包含自我介绍、课堂规则说明</li>
<li>体现亲和力与课堂管理意识</li>
</ol>""",
                semester_id=sem2.id,
                instructor_id=instructors[0].id,
                deadline=datetime(2024, 10, 15, 23, 59, 59),
                require_lesson_plan=False,
                require_video=True,
                is_published=True,
            ),
            Task(
                title="板书设计与粉笔字练习",
                content="""<h3>任务要求</h3>
<p>选择一个教学主题，设计板书布局并拍照上传，同时上传粉笔字练习的照片或视频。</p>
<ol>
<li>板书设计要体现知识结构的逻辑性</li>
<li>书写工整、布局美观</li>
</ol>""",
                semester_id=sem2.id,
                instructor_id=instructors[1].id,
                deadline=datetime(2024, 11, 15, 23, 59, 59),
                require_lesson_plan=True,
                require_video=False,
                is_published=True,
            ),
        ]
        session.add_all(tasks)
        await session.commit()
        print(f"✅ 已创建 {len(tasks)} 个试讲任务")
        print("🎉 演示数据初始化完成！")
        print("   教师账号: T001/T002/T003, 密码: 123456")
        print("   学生账号: S2024001-S2024015, 密码: 123456")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
