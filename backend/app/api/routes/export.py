"""
数据导出路由
提供成绩导出、分析报告导出等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io
import json

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.services.export_service import export_service

router = APIRouter()


@router.get("/grades/csv")
async def export_grades_csv(
    semester_id: int = Query(..., description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    导出成绩为 CSV 文件
    
    老师：导出自己学生的成绩
    管理员：导出全部成绩
    """
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="学生无权导出成绩")
    
    instructor_id = None
    if current_user.role == UserRole.INSTRUCTOR:
        instructor_id = current_user.id
    
    try:
        csv_content = await export_service.export_grades_csv(
            db, semester_id, instructor_id
        )
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode("utf-8-sig")),  # BOM for Excel
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=grades_{semester_id}.csv"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/submissions/csv")
async def export_submissions_csv(
    semester_id: int = Query(..., description="批次ID"),
    task_id: int = Query(None, description="任务ID（可选）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    导出提交记录为 CSV 文件
    """
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="学生无权导出")
    
    instructor_id = None
    if current_user.role == UserRole.INSTRUCTOR:
        instructor_id = current_user.id
    
    try:
        csv_content = await export_service.export_submissions_csv(
            db, semester_id, task_id, instructor_id
        )
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode("utf-8-sig")),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=submissions_{semester_id}.csv"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/analysis/{submission_id}")
async def export_ai_analysis_report(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    导出单个提交的 AI 分析报告（JSON 格式）
    """
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="学生无权导出分析报告")
    
    try:
        report = await export_service.export_ai_analysis_report(db, submission_id)
        
        return StreamingResponse(
            io.BytesIO(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=analysis_{submission_id}.json"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/semester/{semester_id}/summary")
async def export_semester_summary(
    semester_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    导出批次汇总报告（JSON 格式）
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="仅管理员可导出批次汇总")
    
    try:
        report = await export_service.export_semester_summary(db, semester_id)
        
        return StreamingResponse(
            io.BytesIO(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=semester_summary_{semester_id}.json"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/ai-report")
async def export_ai_report(
    semester_id: int = Query(..., description="批次ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI 分析报告导出（Markdown 格式）
    调用 AI 对批次数据生成综合分析报告
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="仅管理员可导出AI分析报告")

    from sqlalchemy import select, func
    from app.models.semester import Semester
    from app.models.group import Group
    from app.models.task import Task
    from app.models.submission import Submission, SubmissionStatus

    sem_result = await db.execute(select(Semester).where(Semester.id == semester_id))
    semester = sem_result.scalar_one_or_none()
    if not semester:
        raise HTTPException(status_code=404, detail="批次不存在")

    groups_result = await db.execute(select(Group).where(Group.semester_id == semester_id))
    groups = list(groups_result.scalars().all())
    student_ids = [g.student_id for g in groups]
    instructor_count = len(set(g.instructor_id for g in groups))

    tasks_result = await db.execute(
        select(Task).where(Task.semester_id == semester_id, Task.is_published == True)
    )
    tasks = list(tasks_result.scalars().all())
    task_ids = [t.id for t in tasks]

    submissions = []
    if task_ids:
        subs_result = await db.execute(
            select(Submission).where(Submission.task_id.in_(task_ids))
        )
        submissions = list(subs_result.scalars().all())

    total_subs = len(submissions)
    approved = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
    rejected = sum(1 for s in submissions if s.status == SubmissionStatus.REJECTED)
    pending = sum(1 for s in submissions if s.status == SubmissionStatus.PENDING)
    scores = [s.total_score for s in submissions if s.total_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    pass_rate = round(approved / total_subs * 100, 1) if total_subs > 0 else 0

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# AI 分析报告 - {semester.name}",
        f"",
        f"> 生成时间：{now}",
        f"",
        f"## 一、基础数据概览",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 学生总数 | {len(student_ids)} |",
        f"| 指导老师 | {instructor_count} |",
        f"| 发布任务 | {len(tasks)} |",
        f"| 提交总数 | {total_subs} |",
        f"| 已通过 | {approved} |",
        f"| 已驳回 | {rejected} |",
        f"| 待批改 | {pending} |",
        f"| 平均成绩 | {avg_score} |",
        f"| 通过率 | {pass_rate}% |",
        f"",
        f"## 二、成绩分布",
        f"",
    ]

    if scores:
        exc = sum(1 for s in scores if s >= 90)
        good = sum(1 for s in scores if 80 <= s < 90)
        med = sum(1 for s in scores if 70 <= s < 80)
        pas = sum(1 for s in scores if 60 <= s < 70)
        fail = sum(1 for s in scores if s < 60)
        tot = len(scores)
        lines += [
            f"| 等级 | 人数 | 占比 |",
            f"|------|------|------|",
            f"| 优秀 (90+) | {exc} | {round(exc/tot*100,1)}% |",
            f"| 良好 (80-89) | {good} | {round(good/tot*100,1)}% |",
            f"| 中等 (70-79) | {med} | {round(med/tot*100,1)}% |",
            f"| 及格 (60-69) | {pas} | {round(pas/tot*100,1)}% |",
            f"| 不及格 (<60) | {fail} | {round(fail/tot*100,1)}% |",
            f"",
        ]
    else:
        lines.append("暂无成绩数据。\n")

    try:
        from app.core.config import settings
        if settings.AI_ENABLED:
            from app.services.ai_model_service import get_dynamic_ai_service
            ai_svc = await get_dynamic_ai_service(db)
            ai_text = await ai_svc.chat_completion(
                messages=[
                    {"role": "system", "content": "你是教育数据分析专家。"},
                    {"role": "user", "content": f"请根据以下数据写200字分析：学生{len(student_ids)}人，提交{total_subs}份，通过率{pass_rate}%，平均分{avg_score}，驳回{rejected}份。"},
                ],
                user_id=current_user.id,
                usage_type="ai_report",
                temperature=0.6,
            )
            lines += [f"## 三、AI 智能分析", f"", ai_text.strip(), f""]
    except Exception:
        lines += [f"## 三、AI 智能分析", f"", f"AI 分析功能暂不可用。", f""]

    lines += [f"---", f"", f"*本报告由试讲管理系统 AI 引擎自动生成*"]
    md_content = "\n".join(lines)

    return StreamingResponse(
        io.BytesIO(md_content.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=ai_report_{semester_id}.md"}
    )
