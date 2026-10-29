"""
检查视频分析功能配置是否正确
"""
import sys
from pathlib import Path
import subprocess

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def check_env_config():
    """检查环境变量配置"""
    print("=" * 60)
    print("1. 检查环境变量配置")
    print("=" * 60)
    
    issues = []
    
    # 检查AI功能是否启用
    if not settings.AI_ENABLED:
        issues.append("❌ AI_ENABLED 未启用，请设置为 true")
    else:
        print("✅ AI_ENABLED: true")
    
    # 检查AI服务商
    print(f"✅ AI_PROVIDER: {settings.AI_PROVIDER}")
    
    # 检查API Key
    if settings.AI_PROVIDER.lower() == "dashscope":
        if not settings.DASHSCOPE_API_KEY:
            issues.append("❌ DASHSCOPE_API_KEY 未配置")
        elif settings.DASHSCOPE_API_KEY == "your_api_key_here":
            issues.append("⚠️  DASHSCOPE_API_KEY 还是默认值，请替换为真实的 API Key")
        else:
            print(f"✅ DASHSCOPE_API_KEY: {settings.DASHSCOPE_API_KEY[:10]}...")
            print(f"✅ DASHSCOPE_MODEL: {settings.DASHSCOPE_MODEL}")
    
    elif settings.AI_PROVIDER.lower() == "openai":
        if not settings.OPENAI_API_KEY:
            issues.append("❌ OPENAI_API_KEY 未配置")
        else:
            print(f"✅ OPENAI_API_KEY: {settings.OPENAI_API_KEY[:10]}...")
            print(f"✅ OPENAI_MODEL: {settings.OPENAI_MODEL}")
    
    # 检查视频分析配置
    print(f"✅ ENABLE_GESTURE_ANALYSIS: {settings.ENABLE_GESTURE_ANALYSIS}")
    
    if hasattr(settings, 'VIDEO_ANALYSIS_PROVIDER'):
        print(f"✅ VIDEO_ANALYSIS_PROVIDER: {settings.VIDEO_ANALYSIS_PROVIDER}")
    else:
        issues.append("⚠️  VIDEO_ANALYSIS_PROVIDER 未配置（将使用默认值）")
    
    print()
    return issues


def check_system_dependencies():
    """检查系统依赖"""
    print("=" * 60)
    print("2. 检查系统依赖")
    print("=" * 60)
    
    issues = []
    
    # 检查 ffmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"✅ ffmpeg 已安装: {version}")
        else:
            issues.append("❌ ffmpeg 未正确安装")
    except FileNotFoundError:
        issues.append("❌ ffmpeg 未安装，请运行: brew install ffmpeg (macOS) 或 sudo apt install ffmpeg (Ubuntu)")
    except Exception as e:
        issues.append(f"❌ 检查 ffmpeg 时出错: {e}")
    
    # 检查 ffprobe
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ ffprobe 已安装")
        else:
            issues.append("❌ ffprobe 未正确安装")
    except FileNotFoundError:
        issues.append("❌ ffprobe 未安装（通常随 ffmpeg 一起安装）")
    except Exception as e:
        issues.append(f"❌ 检查 ffprobe 时出错: {e}")
    
    print()
    return issues


def check_python_packages():
    """检查Python包"""
    print("=" * 60)
    print("3. 检查Python包")
    print("=" * 60)
    
    issues = []
    
    required_packages = [
        ("httpx", "异步HTTP客户端"),
        ("openai", "OpenAI SDK"),
    ]
    
    optional_packages = [
        ("cv2", "opencv-python", "视频处理（动作分析需要）"),
        ("mediapipe", "mediapipe", "动作分析"),
    ]
    
    # 检查必需包
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装 - {description}")
        except ImportError:
            issues.append(f"❌ {package} 未安装 - {description}")
    
    # 检查可选包
    for package, pip_name, description in optional_packages:
        try:
            __import__(package)
            print(f"✅ {pip_name} 已安装 - {description}")
        except ImportError:
            if settings.ENABLE_GESTURE_ANALYSIS:
                issues.append(f"⚠️  {pip_name} 未安装 - {description}（动作分析已启用但缺少依赖）")
            else:
                print(f"⏭️  {pip_name} 未安装 - {description}（可选，动作分析未启用）")
    
    print()
    return issues


def check_database_fields():
    """检查数据库字段"""
    print("=" * 60)
    print("4. 检查数据库字段")
    print("=" * 60)
    
    issues = []
    
    try:
        import asyncio
        from sqlalchemy import text
        from app.core.database import engine
        
        async def check_fields():
            is_mysql = "mysql" in settings.DATABASE_URL.lower()
            
            async with engine.connect() as conn:
                if is_mysql:
                    result = await conn.execute(
                        text("""
                            SELECT COLUMN_NAME 
                            FROM information_schema.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'submissions'
                        """)
                    )
                    columns = [row[0] for row in result.fetchall()]
                else:
                    result = await conn.execute(text("PRAGMA table_info(submissions)"))
                    columns = [row[1] for row in result.fetchall()]
                
                required_fields = [
                    "lesson_plan_analysis",
                    "video_analysis",
                    "ai_suggested_feedback",
                    "ai_suggested_score"
                ]
                
                field_issues = []
                for field in required_fields:
                    if field in columns:
                        print(f"✅ 字段存在: {field}")
                    else:
                        field_issues.append(f"❌ 字段缺失: {field}")
                
                return field_issues
        
        field_issues = asyncio.run(check_fields())
        
        if field_issues:
            issues.extend(field_issues)
            issues.append("💡 请运行: python scripts/add_video_analysis_fields.py")
        
    except Exception as e:
        issues.append(f"❌ 检查数据库字段时出错: {e}")
    
    print()
    return issues


def check_upload_directory():
    """检查上传目录"""
    print("=" * 60)
    print("5. 检查上传目录")
    print("=" * 60)
    
    issues = []
    
    upload_dir = Path(settings.UPLOAD_DIR)
    
    if upload_dir.exists():
        print(f"✅ 上传目录存在: {upload_dir}")
        
        # 检查子目录
        subdirs = ["videos", "lesson_plans"]
        for subdir in subdirs:
            subdir_path = upload_dir / subdir
            if subdir_path.exists():
                print(f"✅ 子目录存在: {subdir}")
            else:
                print(f"⚠️  子目录不存在: {subdir}（将在首次上传时自动创建）")
    else:
        issues.append(f"⚠️  上传目录不存在: {upload_dir}（将在启动时自动创建）")
    
    print()
    return issues


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("视频AI分析功能配置检查")
    print("=" * 60)
    print()
    
    all_issues = []
    
    # 执行所有检查
    all_issues.extend(check_env_config())
    all_issues.extend(check_system_dependencies())
    all_issues.extend(check_python_packages())
    all_issues.extend(check_database_fields())
    all_issues.extend(check_upload_directory())
    
    # 总结
    print("=" * 60)
    print("检查结果总结")
    print("=" * 60)
    
    if not all_issues:
        print("✅ 所有检查通过！视频AI分析功能已正确配置。")
        print()
        print("下一步：")
        print("1. 启动后端服务: uvicorn app.main:app --reload")
        print("2. 测试功能: python scripts/test_video_analysis.py <video_path>")
        print("3. 访问API文档: http://localhost:8000/api/docs")
    else:
        print(f"发现 {len(all_issues)} 个问题：")
        print()
        for issue in all_issues:
            print(issue)
        print()
        print("请根据上述提示修复问题后重新运行此脚本。")
    
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
