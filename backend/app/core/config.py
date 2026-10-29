"""
Application configuration using Pydantic Settings.
"""
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # ==================== App Settings ====================
    APP_NAME: str = Field(default="面向师范生试讲训练的多模态智能赋能系统")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)
    
    # ==================== Database Settings ====================
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./app.db"  # 默认使用SQLite，开箱即用
    )
    DATABASE_ECHO: bool = Field(default=False)
    
    # ==================== JWT Settings ====================
    JWT_SECRET_KEY: str = Field(default="your-super-secret-key-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24)  # 24 hours
    
    # ==================== CORS Settings ====================
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"])
    
    # ==================== File Upload Settings ====================
    UPLOAD_DIR: str = Field(default="./uploads")
    MAX_FILE_SIZE: int = Field(default=500 * 1024 * 1024)  # 500MB
    TRIAL_VIDEO_STORAGE_DIR: str = Field(default="./private_trial_videos")
    TRIAL_VIDEO_MAX_BYTES: int = Field(default=1024 ** 3, gt=0)
    TRIAL_VIDEO_USER_BYTES: int = Field(default=1024 ** 3, gt=0)
    TRIAL_VIDEO_TOTAL_BYTES: int = Field(default=20 * 1024 ** 3, gt=0)
    TRIAL_VIDEO_MIN_FREE_BYTES: int = Field(default=256 * 1024 ** 2, ge=0)
    TRIAL_VIDEO_PRIVATE_DAYS: int = Field(default=15, gt=0)
    ALLOWED_DOCUMENT_TYPES: List[str] = Field(default=["application/pdf"])
    ALLOWED_VIDEO_TYPES: List[str] = Field(
        default=["video/mp4", "video/avi", "video/quicktime", "video/x-msvideo"]
    )
    
    # ==================== AI Settings ====================
    AI_ENABLED: bool = Field(default=True, description="是否启用 AI 功能")
    AI_PROVIDER: str = Field(default="dashscope", description="AI 服务商: dashscope/openai/deepseek")
    
    # 通义千问配置 (默认推荐)
    DASHSCOPE_API_KEY: str = Field(default="", description="通义千问 API Key")
    DASHSCOPE_MODEL: str = Field(default="qwen-plus", description="通义千问文本模型")
    DASHSCOPE_AUDIO_MODEL: str = Field(default="qwen-omni-turbo", description="通义千问音频模型")
    DASHSCOPE_VISION_MODEL: str = Field(default="qwen-vl-max", description="通义千问视觉模型")
    DASHSCOPE_BASE_URL: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    
    # OpenAI 配置
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API Key")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI 模型")
    OPENAI_BASE_URL: str = Field(default="https://api.openai.com/v1")
    
    # DeepSeek 配置
    DEEPSEEK_API_KEY: str = Field(default="", description="DeepSeek API Key")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat", description="DeepSeek 模型")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com/v1")
    
    # AI 通用设置
    AI_MAX_TOKENS: int = Field(default=4096, description="AI 最大输出 token 数")
    AI_TEMPERATURE: float = Field(default=0.7, description="AI 生成温度")
    AI_LESSON_PLAN_MAX_CHARS: int = Field(default=8000, description="备课助手教案内容最大字符数（截断阈值）")
    TEXTBOOK_STORAGE_DIR: str = Field(default="./private_textbooks", description="教材PDF和图片私有目录，不挂载到公共uploads")
    AUDIO_SOURCE_DIR: str = Field(default="", description="英语音频及检索元数据目录；留空使用项目根目录下的音频源文件")
    BOCHA_API_KEY: str = Field(default="", description="博查搜索密钥，仅用于后端教学视频检索")
    BOCHA_BASE_URL: str = Field(default="https://api.bochaai.com", description="博查 API 基址")
    VIDEO_SEARCH_ENABLED: bool = Field(default=True)
    VIDEO_SEARCH_CACHE_HOURS: int = Field(default=24, ge=1, le=168)
    
    # ==================== 视频分析设置 ====================
    ENABLE_GESTURE_ANALYSIS: bool = Field(default=True, description="是否启用视觉分析")
    USE_CLOUD_VISION: bool = Field(default=True, description="是否使用云端视觉分析（否则使用本地MediaPipe）")
    VIDEO_ANALYSIS_PROVIDER: str = Field(default="dashscope", description="视频分析服务商: dashscope/whisper")


# Create global settings instance
settings = Settings()
