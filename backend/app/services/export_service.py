"""
数据导出服务
支持成绩导出、画像报告导出等功能
"""
import io
import csv
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.user import User, UserRole
from app.models.submission import Submission, SubmissionStatus
from app.models.task import Task
from app.models.semester import Semester
from app.models.group import Group


class ExportService:
    """数据导出服务"""
    
    async def export_grades_csv(
        self,
        db: AsyncSession,
        semester_id: int,
        instructor_id: Optional[int] = None
    ) -> str:
        """
        导出成绩为 CSV 格式
        
        Args:
            db: 数据库会话
            semester_id: 批次ID
            instructor_id: 老师ID（可选，仅导出该老师的学生）
            
        Returns:
            CSV 字符串
        """
        # 获取学生列表
        if instructor_id:
            stmt = select(Group.student_id).where(
                and_(
                    Group.semester_id == semester_id,
                    Group.instructor_id == instructor_id
                )
            )
        else:
            stmt = select(Group.student_id).where(
                Group.semester_id == semester_id
            ).distinct()
        
        result = await db.execute(stmt)
        student_ids = [row[0] for row in result.fetchall()]
        
        # 获取任务列表
        task_stmt = select(Task).where(Task.semester_id == semester_id).order_by(Task.created_at)
        task_result = await db.execute(task_stmt)
        tasks = list(task_result.scalars().all())
        
        # 构建 CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 表头
        headers = ["学号", "姓名", "学院", "专业", "班级"]
        for task in tasks:
            headers.extend([f"{task.title}-教案分", f"{task.title}-视频分", f"{task.title}-总分"])
        headers.extend(["平均分", "完成任务数", "通过任务数"])
        writer.writerow(headers)
        
        # 数据行
        for student_id in student_ids:
            student = await db.get(User, student_id)
            if not student:
                continue
            
            row = [
                student.student_id or "",
                student.name or "",
                student.department or "",
                student.major or "",
                student.class_name or ""
            ]
            
            # 获取该学生的所有提交
            sub_stmt = select(Submission).where(
                Submission.student_id == student_id
            ).options(selectinload(Submission.task)).filter(
                Submission.task.has(Task.semester_id == semester_id)
            )
            sub_result = await db.execute(sub_stmt)
            submissions = {s.task_id: s for s in sub_result.scalars().all()}
            
            total_score = 0
            score_count = 0
            completed = 0
            approved = 0
            
            for task in tasks:
                sub = submissions.get(task.id)
                if sub:
                    row.extend([
                        sub.lesson_plan_score or "",
                        sub.video_score or "",
                        sub.total_score or ""
                    ])
                    if sub.total_score:
                        total_score += sub.total_score
                        score_count += 1
                    if sub.status != SubmissionStatus.PENDING:
                        completed += 1
                    if sub.status == SubmissionStatus.APPROVED:
                        approved += 1
                else:
                    row.extend(["", "", ""])
            
            avg_score = round(total_score / score_count, 1) if score_count > 0 else ""
            row.extend([avg_score, completed, approved])
            writer.writerow(row)
        
        return output.getvalue()
    
    async def export_submissions_csv(
        self,
        db: AsyncSession,
        semester_id: int,
        task_id: Optional[int] = None,
        instructor_id: Optional[int] = None
    ) -> str:
        """
        导出提交记录为 CSV 格式
        """
        stmt = select(Submission).options(
            selectinload(Submission.student),
            selectinload(Submission.task)
        )
        
        if task_id:
            stmt = stmt.where(Submission.task_id == task_id)
        else:
            stmt = stmt.join(Task).where(Task.semester_id == semester_id)
        
        if instructor_id:
            # 筛选该老师的学生
            sub_stmt = select(Group.student_id).where(
                and_(
                    Group.semester_id == semester_id,
                    Group.instructor_id == instructor_id
                )
            )
            sub_result = await db.execute(sub_stmt)
            student_ids = [row[0] for row in sub_result.fetchall()]
            stmt = stmt.where(Submission.student_id.in_(student_ids))
        
        result = await db.execute(stmt.order_by(Submission.created_at.desc()))
        submissions = list(result.scalars().all())
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        headers = [
            "提交ID", "任务名称", "学号", "姓名", 
            "教案分", "视频分", "总分", "AI建议分",
            "状态", "提交时间", "评阅时间", "评语"
        ]
        writer.writerow(headers)
        
        status_map = {
            SubmissionStatus.PENDING: "待批改",
            SubmissionStatus.GRADED: "已评分",
            SubmissionStatus.APPROVED: "已通过",
            SubmissionStatus.REJECTED: "已驳回"
        }
        
        for sub in submissions:
            row = [
                sub.id,
                sub.task.title if sub.task else "",
                sub.student.student_id if sub.student else "",
                sub.student.name if sub.student else "",
                sub.lesson_plan_score or "",
                sub.video_score or "",
                sub.total_score or "",
                sub.ai_suggested_score or "",
                status_map.get(sub.status, ""),
                sub.submitted_at.strftime("%Y-%m-%d %H:%M") if sub.submitted_at else "",
                sub.reviewed_at.strftime("%Y-%m-%d %H:%M") if sub.reviewed_at else "",
                sub.feedback or ""
            ]
            writer.writerow(row)
        
        return output.getvalue()
    
    async def export_ai_analysis_report(
        self,
        db: AsyncSession,
        submission_id: int
    ) -> Dict[str, Any]:
        """
        导出单个提交的 AI 分析报告
        """
        submission = await db.get(Submission, submission_id)
        if not submission:
            raise ValueError("提交不存在")
        
        student = await db.get(User, submission.student_id)
        task = await db.get(Task, submission.task_id)
        
        report = {
            "export_time": datetime.now().isoformat(),
            "student": {
                "id": student.id if student else None,
                "name": student.name if student else None,
                "student_id": student.student_id if student else None
            },
            "task": {
                "id": task.id if task else None,
                "title": task.title if task else None
            },
            "submission": {
                "id": submission.id,
                "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
                "status": submission.status.value if submission.status else None
            },
            "scores": {
                "lesson_plan": submission.lesson_plan_score,
                "video": submission.video_score,
                "total": submission.total_score,
                "ai_suggested": submission.ai_suggested_score
            },
            "feedback": submission.feedback,
            "ai_feedback": submission.ai_suggested_feedback,
            "lesson_plan_analysis": json.loads(submission.lesson_plan_analysis) if submission.lesson_plan_analysis else None,
            "video_analysis": json.loads(submission.video_analysis) if submission.video_analysis else None
        }
        
        return report
    
    async def export_semester_summary(
        self,
        db: AsyncSession,
        semester_id: int
    ) -> Dict[str, Any]:
        """
        导出批次汇总报告
        """
        # 批次信息
        semester = await db.get(Semester, semester_id)
        if not semester:
            raise ValueError("批次不存在")
        
        # 任务统计
        task_stmt = select(Task).where(Task.semester_id == semester_id)
        task_result = await db.execute(task_stmt)
        tasks = list(task_result.scalars().all())
        
        # 提交统计
        sub_stmt = select(Submission).join(Task).where(Task.semester_id == semester_id)
        sub_result = await db.execute(sub_stmt)
        submissions = list(sub_result.scalars().all())
        
        # 学生统计
        student_stmt = select(Group.student_id).where(
            Group.semester_id == semester_id
        ).distinct()
        student_result = await db.execute(student_stmt)
        student_count = len(list(student_result.fetchall()))
        
        # 计算统计数据
        total_submissions = len(submissions)
        approved_count = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
        graded_count = sum(1 for s in submissions if s.status in [SubmissionStatus.GRADED, SubmissionStatus.APPROVED])
        
        scores = [s.total_score for s in submissions if s.total_score]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # 分数分布
        distribution = {
            "90以上": sum(1 for s in scores if s >= 90),
            "80-89": sum(1 for s in scores if 80 <= s < 90),
            "70-79": sum(1 for s in scores if 70 <= s < 80),
            "60-69": sum(1 for s in scores if 60 <= s < 70),
            "60以下": sum(1 for s in scores if s < 60)
        }
        
        return {
            "export_time": datetime.now().isoformat(),
            "semester": {
                "id": semester.id,
                "name": semester.name,
                "start_date": semester.start_date.isoformat() if semester.start_date else None,
                "end_date": semester.end_date.isoformat() if semester.end_date else None,
                "status": semester.status.value if semester.status else None
            },
            "statistics": {
                "task_count": len(tasks),
                "student_count": student_count,
                "total_submissions": total_submissions,
                "graded_submissions": graded_count,
                "approved_submissions": approved_count,
                "average_score": round(avg_score, 1),
                "score_distribution": distribution
            },
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "deadline": t.deadline.isoformat() if t.deadline else None
                }
                for t in tasks
            ]
        }


# 全局服务实例
export_service = ExportService()
