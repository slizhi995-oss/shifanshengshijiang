"""
FastAPI application entry point.
面向师范生试讲训练的多模态智能赋能系统
"""
from contextlib import asynccontextmanager
import asyncio
from contextlib import suppress
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.console import configure_console_output

# Windows may use GBK for redirected output. Startup and request logs must not
# stop the application when they contain emoji or other unsupported characters.
configure_console_output()

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    print("=" * 50)
    print(f"🚀 {settings.APP_NAME}")
    print(f"📌 Version: {settings.APP_VERSION}")
    print("=" * 50)
    
    # Startup - Auto initialize database if needed
    await init_db()
    from app.services.trial_videos import maintenance, storage_root, recover_interrupted_analysis
    storage_root()
    await recover_interrupted_analysis()
    video_cleanup = asyncio.create_task(maintenance())
    
    # Create upload directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    print(f"📁 上传目录: {settings.UPLOAD_DIR}")
    
    print("=" * 50)
    print("🎉 服务启动成功!")
    print("📖 API文档: /api/docs（使用当前服务地址访问）")
    print("=" * 50)
    
    try:
        yield
    finally:
        video_cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await video_cleanup
    
    # Shutdown
    print("👋 服务正在关闭...")
    await close_db()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="面向师范生试讲训练的多模态智能赋能系统 API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure upload directory exists before mounting
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API health check."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
