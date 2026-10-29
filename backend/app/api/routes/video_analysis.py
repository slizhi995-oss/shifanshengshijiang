"""
视频分析 API 路由
提供视频AI分析功能
"""
import os
import uuid
import json
import hashlib
import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_instructor
from app.models.user import User
from app.models.submission import Submission
from app.services.video_analysis_service import get_video_analysis_service
from app.services.ai_model_service import get_dynamic_ai_service

router = APIRouter()

# 独立视频分析结果的内存缓存 (生产环境应使用 Redis 等)
_standalone_analysis_results: Dict[str, Dict[str, Any]] = {}
# 文件哈希 → task_id 映射，用于去重
_hash_to_task: Dict[str, str] = {}

# ==================== 演示模式：预置分析结果 ====================
_DEMO_ANALYSIS = {
    "overall_score": 82,
    "speech_rate": 146,
    "pause_count": 5,
    "filler_word_count": 3,
    "duration": 127,
    "transcript": "同学们好，今天我们来学习三角形的面积。首先，我们回顾一下之前学过的平行四边形的面积公式。大家还记得吗？对，底乘以高。那三角形和平行四边形之间有什么关系呢？我们来看这个图形。如果我们沿着对角线把一个平行四边形剪开，会得到什么？对，两个完全一样的三角形。所以三角形的面积就是底乘以高再除以二。让我们来做几道练习题巩固一下。第一题，一个三角形的底是8厘米，高是5厘米，它的面积是多少？",
    "gesture_analysis": {
        "posture_score": 78,
        "gesture_score": 85,
        "eye_contact_score": 80,
        "expression_score": 76,
        "space_usage": "中等",
        "hand_gesture_frequency": "适中"
    },
    "suggestions": [
        "语速整体适中(146字/分钟)，建议在重点内容处适当放慢，给学生思考时间",
        "手势运用自然大方，可以在板书时增加指示性手势，引导学生视线",
        "与学生互动环节设计合理，可以增加等待回答的时间，鼓励更多学生参与",
        "表情自然亲切，建议在提问环节增加更多微笑和鼓励性表情",
        "站姿端正但活动范围偏小，可以适当在讲台前移动，增强课堂活力"
    ],
    "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "audio_seconds": 0},
}


@router.post(
    "/demo-analyze",
    response_model=Dict[str, Any],
    summary="演示模式：立即返回预置视频分析结果",
)
async def demo_analyze_video(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """演示模式：跳过上传和分析，直接返回预置结果"""
    task_id = uuid.uuid4().hex
    _standalone_analysis_results[task_id] = {
        "status": "completed",
        "user_id": current_user.id,
        "filename": "demo_video.mp4",
        "analysis": _DEMO_ANALYSIS,
        "reused": False,
    }
    return {
        "message": "演示模式：分析结果已就绪",
        "task_id": task_id,
        "status": "completed",
    }


@router.post(
    "/upload-analyze",
    response_model=Dict[str, Any],
    summary="上传视频进行独立AI分析",
)
async def upload_and_analyze_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    上传视频文件进行独立AI分析（不需要关联提交记录）
    
    支持 mp4, avi, mov, webm, mkv 格式，最大 500MB
    返回 task_id，可通过 GET /video-analysis/standalone/{task_id} 查询结果
    """
    # 检查文件类型
    allowed_exts = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".flv", ".wmv"}
    filename = video.filename or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的视频格式: {ext}，支持: {', '.join(allowed_exts)}"
        )
    
    # 保存上传文件
    upload_dir = os.path.join(settings.UPLOAD_DIR, "standalone_videos")
    os.makedirs(upload_dir, exist_ok=True)
    
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, unique_name)
    
    content = await video.read()
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="视频文件不能超过 500MB")
    
    # 计算文件 SHA-256 哈希用于去重
    file_hash = hashlib.sha256(content).hexdigest()
    
    # 检查是否已有相同视频的分析结果
    existing_task_id = _hash_to_task.get(file_hash)
    if existing_task_id:
        existing = _standalone_analysis_results.get(existing_task_id)
        if existing and existing.get("status") == "completed":
            # 已有完成的分析，直接复用
            new_task_id = uuid.uuid4().hex
            _standalone_analysis_results[new_task_id] = {
                **existing,
                "user_id": current_user.id,
                "filename": filename,
                "reused": True,
                "original_task_id": existing_task_id,
            }
            print(f"♻️ 视频去重命中: hash={file_hash[:12]}..., 复用 task={existing_task_id[:8]}")
            return {
                "message": "该视频已分析过，直接返回结果",
                "task_id": new_task_id,
                "status": "completed",
                "reused": True,
            }
        elif existing and existing.get("status") == "processing" and existing.get("user_id") == current_user.id:
            # 正在处理中，返回现有 task_id 让前端轮询
            print(f"⏳ 视频去重命中(处理中): hash={file_hash[:12]}..., task={existing_task_id[:8]}")
            return {
                "message": "该视频正在分析中，请等待结果",
                "task_id": existing_task_id,
                "status": "processing",
                "reused": True,
            }
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 生成任务ID
    task_id = uuid.uuid4().hex
    _standalone_analysis_results[task_id] = {
        "status": "processing",
        "user_id": current_user.id,
        "filename": filename,
        "file_hash": file_hash,
    }
    # 记录哈希映射
    _hash_to_task[file_hash] = task_id
    
    # 后台执行分析
    background_tasks.add_task(
        _analyze_standalone_video,
        task_id=task_id,
        video_path=file_path,
    )
    
    return {
        "message": "视频分析任务已启动，请稍后查询结果",
        "task_id": task_id,
        "status": "processing",
    }


async def _analyze_standalone_video(task_id: str, video_path: str):
    """后台任务：独立视频分析"""
    import traceback
    try:
        video_service = get_video_analysis_service()
        analysis_result = await video_service.analyze_video(video_path)
        
        _standalone_analysis_results[task_id] = {
            **_standalone_analysis_results.get(task_id, {}),
            "status": "completed",
            "analysis": analysis_result,
        }
        print(f"✅ 独立视频分析完成: task_id={task_id}")
    except Exception as e:
        traceback.print_exc()
        _standalone_analysis_results[task_id] = {
            **_standalone_analysis_results.get(task_id, {}),
            "status": "failed",
            "error": str(e) or f"视频评估失败（{type(e).__name__}），请稍后重试",
            "message": "视频分析失败，请检查视频格式或联系管理员",
        }
        print(f"❌ 独立视频分析失败: task_id={task_id}, error={e}")
    finally:
        # 清理临时视频文件
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                # 清理可能产生的音频临时文件
                audio_path = video_path.rsplit(".", 1)[0] + "_audio.wav"
                if os.path.exists(audio_path):
                    os.remove(audio_path)
        except Exception:
            pass


@router.get(
    "/check-hash/{file_hash}",
    response_model=Dict[str, Any],
    summary="根据文件哈希检查视频是否已分析",
)
async def check_video_hash(
    file_hash: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    前端先计算文件 SHA-256 哈希，调用此接口检查是否已有分析结果。
    如果有，返回 task_id 和状态，前端可直接跳过上传。
    """
    existing_task_id = _hash_to_task.get(file_hash)
    if not existing_task_id:
        return {"exists": False}
    
    existing = _standalone_analysis_results.get(existing_task_id)
    if not existing:
        return {"exists": False}
    
    if existing.get("status") == "completed":
        # 为当前用户创建新的 task_id 引用
        new_task_id = uuid.uuid4().hex
        _standalone_analysis_results[new_task_id] = {
            **existing,
            "user_id": current_user.id,
            "reused": True,
            "original_task_id": existing_task_id,
        }
        print(f"♻️ 哈希预检命中: hash={file_hash[:12]}..., 复用 task={existing_task_id[:8]}")
        return {
            "exists": True,
            "task_id": new_task_id,
            "status": "completed",
        }
    elif existing.get("status") == "processing" and existing.get("user_id") == current_user.id:
        return {
            "exists": True,
            "task_id": existing_task_id,
            "status": "processing",
        }
    
    return {"exists": False}


@router.get(
    "/standalone/{task_id}",
    response_model=Dict[str, Any],
    summary="查询独立视频分析结果",
)
async def get_standalone_analysis(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    查询独立视频分析任务的结果
    """
    result = _standalone_analysis_results.get(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="分析任务不存在或已过期")
    
    # 权限检查
    if result.get("user_id") != current_user.id and current_user.role not in ("admin", "super_admin", "instructor"):
        raise HTTPException(status_code=403, detail="无权查看")
    
    return result


@router.get(
    "/usage-stats",
    response_model=Dict[str, Any],
    summary="获取视频分析使用统计",
)
async def get_usage_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    获取视频分析的 Token 使用统计
    
    统计所有已分析视频的 token 消耗
    """
    # 查询所有有分析结果的提交
    query = select(Submission.video_analysis).where(
        Submission.video_analysis.isnot(None)
    )
    
    # 如果是学生，只统计自己的
    if current_user.role == "student":
        query = query.where(Submission.student_id == current_user.id)
    
    result = await db.execute(query)
    analyses = result.scalars().all()
    
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    total_audio_seconds = 0
    analysis_count = 0
    
    for analysis_json in analyses:
        if not analysis_json:
            continue
        try:
            analysis = json.loads(analysis_json)
            # 跳过失败的分析
            if analysis.get("status") == "failed":
                continue
            
            token_usage = analysis.get("token_usage", {})
            if token_usage:
                total_input_tokens += token_usage.get("input_tokens", 0)
                total_output_tokens += token_usage.get("output_tokens", 0)
                total_tokens += token_usage.get("total_tokens", 0)
                total_audio_seconds += token_usage.get("audio_seconds", 0)
                analysis_count += 1
        except json.JSONDecodeError:
            continue
    
    return {
        "analysis_count": analysis_count,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "total_audio_seconds": round(total_audio_seconds, 1),
        "console_url": "https://dashscope.console.aliyun.com/",
        "note": "Token 余额请前往阿里云控制台查看"
    }


async def analyze_video_background(
    submission_id: int,
    video_path: str,
    db_url: str,
):
    """
    后台任务：分析视频
    
    Args:
        submission_id: 提交记录ID
        video_path: 视频文件路径
        db_url: 数据库连接URL
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    import traceback
    
    # 创建新的数据库会话（后台任务需要独立会话）
    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    try:
        video_service = get_video_analysis_service()
        
        # 执行视频分析
        full_path = os.path.join(settings.UPLOAD_DIR, video_path)
        analysis_result = await video_service.analyze_video(full_path)
        
        # 保存分析结果到数据库
        async with async_session() as session:
            submission = await session.get(Submission, submission_id)
            if submission:
                submission.video_analysis = json.dumps(analysis_result, ensure_ascii=False)
                await session.commit()
        
        print(f"✅ 视频分析完成: submission_id={submission_id}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 视频分析失败: submission_id={submission_id}, error={error_msg}")
        traceback.print_exc()
        
        # 保存错误信息到数据库，让用户知道分析失败了
        try:
            async with async_session() as session:
                submission = await session.get(Submission, submission_id)
                if submission:
                    error_result = {
                        "status": "failed",
                        "error": error_msg,
                        "message": "视频分析失败，请检查视频格式或联系管理员"
                    }
                    submission.video_analysis = json.dumps(error_result, ensure_ascii=False)
                    await session.commit()
        except Exception as save_error:
            print(f"保存错误信息失败: {save_error}")
    finally:
        await engine.dispose()


@router.post(
    "/submissions/{submission_id}/analyze-video",
    response_model=Dict[str, Any],
    summary="触发视频AI分析",
)
async def trigger_video_analysis(
    submission_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    触发视频AI分析（异步后台任务）
    
    学生提交视频后自动调用，或老师手动触发重新分析
    """
    # 获取提交记录
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    # 权限检查：学生只能分析自己的，老师可以分析学生的
    if current_user.role == "student" and submission.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作")
    
    # 检查是否有视频
    if not submission.video_path:
        raise HTTPException(status_code=400, detail="该提交没有视频文件")
    
    # 检查视频文件是否存在
    video_full_path = os.path.join(settings.UPLOAD_DIR, submission.video_path)
    if not os.path.exists(video_full_path):
        raise HTTPException(status_code=404, detail="视频文件不存在")
    
    # 检查是否已有分析结果
    if submission.video_analysis:
        return {
            "message": "视频已分析过，如需重新分析请使用 force=true",
            "analysis": json.loads(submission.video_analysis)
        }
    
    # 添加后台任务
    background_tasks.add_task(
        analyze_video_background,
        submission_id=submission_id,
        video_path=submission.video_path,
        db_url=settings.DATABASE_URL,
    )
    
    return {
        "message": "视频分析任务已启动，请稍后查询结果",
        "submission_id": submission_id,
        "status": "processing"
    }


@router.post(
    "/submissions/{submission_id}/reanalyze-video",
    response_model=Dict[str, Any],
    summary="重新分析视频",
)
async def reanalyze_video(
    submission_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> Dict[str, Any]:
    """
    重新分析视频（强制覆盖已有结果）
    
    仅老师可用
    """
    # 获取提交记录
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    # 检查是否有视频
    if not submission.video_path:
        raise HTTPException(status_code=400, detail="该提交没有视频文件")
    
    # 清除旧的分析结果
    submission.video_analysis = None
    await db.commit()
    
    # 添加后台任务
    background_tasks.add_task(
        analyze_video_background,
        submission_id=submission_id,
        video_path=submission.video_path,
        db_url=settings.DATABASE_URL,
    )
    
    return {
        "message": "视频重新分析任务已启动",
        "submission_id": submission_id,
        "status": "processing"
    }


@router.get(
    "/submissions/{submission_id}/video-analysis",
    response_model=Dict[str, Any],
    summary="获取视频分析结果",
)
async def get_video_analysis(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    获取视频分析结果
    
    学生可以查看自己的，老师可以查看学生的
    """
    # 获取提交记录
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    # 权限检查
    if current_user.role == "student" and submission.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看")
    
    # 检查是否有分析结果
    if not submission.video_analysis:
        return {
            "status": "not_analyzed",
            "message": "视频尚未分析，请点击提交或等待分析完成"
        }
    
    try:
        analysis = json.loads(submission.video_analysis)
        
        # 检查是否是错误结果
        if isinstance(analysis, dict) and analysis.get("status") == "failed":
            return {
                "status": "failed",
                "message": analysis.get("message", "分析失败"),
                "error": analysis.get("error", "未知错误")
            }
        
        return {
            "status": "completed",
            "analysis": analysis
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="分析结果解析失败")


@router.post(
    "/submissions/{submission_id}/generate-ai-feedback",
    response_model=Dict[str, Any],
    summary="生成AI综合评语",
)
async def generate_ai_feedback(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_instructor),
) -> Dict[str, Any]:
    """
    基于教案和视频分析结果，生成AI综合评语和建议分数
    
    仅老师可用
    """
    # 获取提交记录
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    
    # 检查是否有分析结果
    lesson_plan_analysis = None
    video_analysis = None
    
    if submission.lesson_plan_analysis:
        try:
            lesson_plan_analysis = json.loads(submission.lesson_plan_analysis)
        except json.JSONDecodeError:
            pass
    
    if submission.video_analysis:
        try:
            video_analysis = json.loads(submission.video_analysis)
        except json.JSONDecodeError:
            pass
    
    if not lesson_plan_analysis and not video_analysis:
        raise HTTPException(
            status_code=400,
            detail="教案和视频都未分析，无法生成评语"
        )
    
    # 构建综合分析结果
    combined_analysis = {
        "lesson_plan": lesson_plan_analysis,
        "video": video_analysis,
    }
    
    # 调用AI生成评语
    ai_service = get_dynamic_ai_service()
    
    try:
        feedback = await ai_service.generate_feedback(
            db=db,
            analysis_result=combined_analysis,
            user_id=submission.student_id
        )
        
        # 计算建议分数
        suggested_score = _calculate_suggested_score(
            lesson_plan_analysis,
            video_analysis
        )
        
        # 保存到数据库
        submission.ai_suggested_feedback = feedback
        submission.ai_suggested_score = suggested_score
        await db.commit()
        
        return {
            "feedback": feedback,
            "suggested_score": suggested_score,
            "lesson_plan_score": lesson_plan_analysis.get("overall_score") if lesson_plan_analysis else None,
            "video_score": video_analysis.get("overall_score") if video_analysis else None,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"生成评语失败: {str(e)}"
        )


def _calculate_suggested_score(
    lesson_plan_analysis: Optional[Dict[str, Any]],
    video_analysis: Optional[Dict[str, Any]],
) -> float:
    """
    计算建议总分
    
    根据配置的权重计算（默认教案40%，视频60%）
    """
    lesson_plan_weight = 0.4
    video_weight = 0.6
    
    lesson_plan_score = 0
    video_score = 0
    
    if lesson_plan_analysis:
        lesson_plan_score = lesson_plan_analysis.get("overall_score", 0)
    
    if video_analysis:
        video_score = video_analysis.get("overall_score", 0)
    
    # 如果只有一个，则该项占100%
    if lesson_plan_analysis and not video_analysis:
        return round(lesson_plan_score, 1)
    elif video_analysis and not lesson_plan_analysis:
        return round(video_score, 1)
    else:
        total = lesson_plan_score * lesson_plan_weight + video_score * video_weight
        return round(total, 1)
