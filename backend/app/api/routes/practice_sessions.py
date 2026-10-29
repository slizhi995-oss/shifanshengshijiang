"""
备课助手会话路由
提供会话持久化、历史记录、报告入库等功能
"""
import json
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.profile import PracticeSession
from app.services.ai_model_service import get_dynamic_ai_service

router = APIRouter()


# ==================== 请求/响应模型 ====================

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    title: Optional[str] = Field(None, description="会话标题")
    submission_id: Optional[int] = Field(None, description="关联的提交ID")
    grade: str = Field("小学四年级", description="年级")
    personality: str = Field("normal", description="AI性格类型")
    lesson_plan_text: Optional[str] = Field(None, description="教案文本")


class SaveMessagesRequest(BaseModel):
    """保存对话消息请求"""
    session_id: int = Field(..., description="会话ID")
    messages: List[dict] = Field(..., description="消息列表")


class SaveReportRequest(BaseModel):
    """保存练习报告请求"""
    session_id: int = Field(..., description="会话ID")
    report: dict = Field(..., description="报告内容")


# ==================== API 路由 ====================

@router.get("")
async def list_practice_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户的练习会话列表
    """
    stmt = select(PracticeSession).where(
        PracticeSession.student_id == current_user.id
    ).order_by(desc(PracticeSession.created_at))
    
    # 分页
    result = await db.execute(
        stmt.limit(page_size).offset((page - 1) * page_size)
    )
    sessions = list(result.scalars().all())
    
    # 总数
    count_result = await db.execute(
        select(PracticeSession).where(
            PracticeSession.student_id == current_user.id
        )
    )
    total = len(list(count_result.scalars().all()))
    
    return {
        "success": True,
        "data": {
            "items": [
                {
                    "id": s.id,
                    "title": s.title,
                    "grade": s.grade,
                    "personality": s.personality,
                    "message_count": s.message_count,
                    "overall_rating": s.overall_rating,
                    "has_report": s.report_json is not None,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }


@router.post("")
async def create_practice_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建新的练习会话
    """
    session = PracticeSession(
        student_id=current_user.id,
        submission_id=request.submission_id,
        title=request.title or f"练习_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        grade=request.grade,
        personality=request.personality,
        started_at=datetime.utcnow(),
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return {
        "success": True,
        "data": {
            "id": session.id,
            "title": session.title,
            "grade": session.grade,
            "personality": session.personality,
        },
        "message": "会话创建成功"
    }


@router.get("/{session_id}")
async def get_practice_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取会话详情（包含消息历史和报告）
    """
    session = await db.get(PracticeSession, session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.student_id != current_user.id and current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="无权查看此会话")
    
    return {
        "success": True,
        "data": {
            "id": session.id,
            "title": session.title,
            "grade": session.grade,
            "personality": session.personality,
            "message_count": session.message_count,
            "overall_rating": session.overall_rating,
            "messages": json.loads(session.messages_json) if session.messages_json else [],
            "report": json.loads(session.report_json) if session.report_json else None,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        }
    }


@router.put("/{session_id}/messages")
async def save_session_messages(
    session_id: int,
    messages: List[dict] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    保存/更新会话消息
    """
    session = await db.get(PracticeSession, session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改此会话")
    
    session.messages_json = json.dumps(messages, ensure_ascii=False)
    session.message_count = len([m for m in messages if m.get("role") in ["user", "assistant"]])
    
    await db.commit()
    
    return {
        "success": True,
        "message": "消息已保存"
    }


@router.post("/{session_id}/report")
async def generate_and_save_report(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    生成并保存练习报告
    """
    session = await db.get(PracticeSession, session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此会话")
    
    if not session.messages_json:
        raise HTTPException(status_code=400, detail="会话没有对话记录")
    
    messages = json.loads(session.messages_json)
    
    if len(messages) < 2:
        raise HTTPException(status_code=400, detail="对话轮数过少，无法生成报告")
    
    try:
        ai_service = get_dynamic_ai_service()
        report = await ai_service.generate_practice_report(
            db=db,
            conversation_history=messages,
            user_id=current_user.id
        )
        
        # 保存报告
        session.report_json = json.dumps(report, ensure_ascii=False)
        session.ended_at = datetime.utcnow()
        
        # 提取整体评分
        if "overall_rating" in report:
            session.overall_rating = float(report["overall_rating"])
        elif "score" in report:
            session.overall_rating = float(report["score"])
        
        await db.commit()
        
        return {
            "success": True,
            "data": report,
            "message": "报告生成成功"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")


@router.delete("/{session_id}")
async def delete_practice_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除练习会话
    """
    session = await db.get(PracticeSession, session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此会话")
    
    await db.delete(session)
    await db.commit()
    
    return {
        "success": True,
        "message": "会话已删除"
    }


# ==================== 统计接口 ====================

@router.get("/stats/me")
async def get_my_practice_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户的练习统计
    """
    stmt = select(PracticeSession).where(
        PracticeSession.student_id == current_user.id
    )
    result = await db.execute(stmt)
    sessions = list(result.scalars().all())
    
    total_sessions = len(sessions)
    completed_sessions = sum(1 for s in sessions if s.report_json)
    total_messages = sum(s.message_count for s in sessions)
    
    # 平均评分
    ratings = [s.overall_rating for s in sessions if s.overall_rating]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    return {
        "success": True,
        "data": {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "total_messages": total_messages,
            "average_rating": round(avg_rating, 1)
        }
    }
