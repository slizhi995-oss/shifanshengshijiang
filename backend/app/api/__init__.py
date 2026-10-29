# API Routes
from fastapi import APIRouter

from app.api.routes import (
    auth, users, semesters, assignments, tasks, submissions, 
    notices, messages, admin, system, grades, chat, ai, 
    video_analysis, profile, ai_ops, practice_sessions, export,
    statistics, rubrics, notifications, logs, ai_model_config,
    data_screen, instructor_ai, admin_ai, resources, textbooks, trial_videos, teaching_tips
)

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(semesters.router, prefix="/semesters", tags=["批次管理"])
api_router.include_router(assignments.router, prefix="/assignments", tags=["分组分配"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["任务管理"])
api_router.include_router(submissions.router, prefix="/submissions", tags=["作业提交"])
api_router.include_router(notices.router, prefix="/notices", tags=["通知公告"])
api_router.include_router(messages.router, prefix="/messages", tags=["消息留言"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理员"])
api_router.include_router(system.router, prefix="/system", tags=["系统设置"])
api_router.include_router(grades.router, prefix="/grades", tags=["学生成绩"])
api_router.include_router(chat.router, prefix="/chat", tags=["师生聊天"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI智能功能"])
api_router.include_router(video_analysis.router, prefix="/video-analysis", tags=["视频分析"])
api_router.include_router(profile.router, prefix="/profile", tags=["成长画像"])
api_router.include_router(ai_ops.router, prefix="/admin/ai-ops", tags=["AI运营看板"])
api_router.include_router(practice_sessions.router, prefix="/practice-sessions", tags=["备课练习会话"])
api_router.include_router(export.router, prefix="/export", tags=["数据导出"])
api_router.include_router(statistics.router, prefix="/statistics", tags=["统计数据"])
api_router.include_router(rubrics.router, prefix="/rubrics", tags=["评分规则"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知中心"])
api_router.include_router(logs.router, prefix="/admin", tags=["系统日志"])
api_router.include_router(ai_model_config.router, prefix="/admin/ai-models", tags=["AI模型配置"])
api_router.include_router(data_screen.router, prefix="/admin/data-screen", tags=["数据大屏"])
api_router.include_router(instructor_ai.router, prefix="/instructor", tags=["导师AI功能"])
api_router.include_router(admin_ai.router, prefix="/admin", tags=["管理员AI功能"])
api_router.include_router(resources.router, prefix="/resources", tags=["资源中心"])
api_router.include_router(textbooks.router, prefix="/textbooks", tags=["教材与教学素材"])
api_router.include_router(trial_videos.router, prefix="/trial-videos", tags=["试讲学习"])
api_router.include_router(teaching_tips.router, tags=["试讲技巧视频"])

