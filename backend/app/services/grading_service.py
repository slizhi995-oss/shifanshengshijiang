"""
综合 AI 批改服务
结合教案分析 + 视频分析，生成综合评估报告和建议评分
这是老师端 AI 辅助批改的核心功能
"""
import json
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.submission import Submission
from app.services.ai_model_service import get_dynamic_ai_service
from app.services.document_parser import DocumentParser
from app.core.config import settings


class ComprehensiveGradingService:
    """
    综合批改服务
    结合教案分析和视频分析，生成综合评估
    """
    
    # 权重配置（后续可从系统设置读取）
    DEFAULT_WEIGHTS = {
        "lesson_plan": 0.4,  # 教案占比 40%
        "video": 0.6,        # 视频占比 60%
    }
    
    async def generate_comprehensive_feedback(
        self,
        db: AsyncSession,
        submission_id: int,
        custom_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        生成综合评估反馈
        
        Args:
            db: 数据库会话
            submission_id: 提交ID
            custom_weights: 自定义权重
            
        Returns:
            综合评估结果
        """
        submission = await db.get(Submission, submission_id)
        if not submission:
            raise ValueError("提交记录不存在")
        
        weights = custom_weights or self.DEFAULT_WEIGHTS
        
        # 收集分析结果
        lesson_plan_analysis = None
        video_analysis = None
        
        if submission.lesson_plan_analysis:
            try:
                lesson_plan_analysis = json.loads(submission.lesson_plan_analysis)
            except:
                pass
        
        if submission.video_analysis:
            try:
                video_analysis = json.loads(submission.video_analysis)
            except:
                pass
        
        # 计算建议分数
        suggested_scores = self._calculate_suggested_scores(
            lesson_plan_analysis, video_analysis, weights
        )
        
        # 生成综合评语
        comprehensive_feedback = await self._generate_ai_feedback(
            db, submission.student_id, lesson_plan_analysis, video_analysis, suggested_scores
        )
        
        # 汇总亮点和改进建议
        highlights = self._extract_highlights(lesson_plan_analysis, video_analysis)
        improvements = self._extract_improvements(lesson_plan_analysis, video_analysis)
        
        result = {
            "suggested_scores": suggested_scores,
            "feedback": comprehensive_feedback,
            "highlights": highlights,
            "improvements": improvements,
            "analysis_summary": {
                "has_lesson_plan_analysis": lesson_plan_analysis is not None,
                "has_video_analysis": video_analysis is not None,
                "weights": weights
            }
        }
        
        # 保存到提交记录
        submission.ai_suggested_score = suggested_scores.get("total_score")
        submission.ai_suggested_feedback = comprehensive_feedback
        await db.commit()
        
        return result
    
    def _calculate_suggested_scores(
        self,
        lesson_plan_analysis: Optional[Dict],
        video_analysis: Optional[Dict],
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """计算建议分数"""
        scores = {
            "lesson_plan_score": 0,
            "video_score": 0,
            "total_score": 0
        }
        
        # 教案分数
        if lesson_plan_analysis:
            overall = lesson_plan_analysis.get("overall_score")
            if overall:
                scores["lesson_plan_score"] = float(overall)
            else:
                # 从维度分数计算
                dimensions = lesson_plan_analysis.get("dimensions", {})
                dim_scores = [
                    d.get("score", 0) for d in dimensions.values()
                    if isinstance(d, dict) and "score" in d
                ]
                if dim_scores:
                    scores["lesson_plan_score"] = sum(dim_scores) / len(dim_scores)
        
        # 视频分数
        if video_analysis:
            overall = video_analysis.get("overall_score")
            if overall:
                scores["video_score"] = float(overall)
            else:
                # 从语速、停顿、手势等推算
                speech_score = self._calculate_speech_score(video_analysis)
                gesture = video_analysis.get("gesture_analysis", {})
                gesture_score = gesture.get("overall_score", 70) if gesture else 70
                scores["video_score"] = (speech_score + gesture_score) / 2
        
        # 计算总分
        if scores["lesson_plan_score"] > 0 and scores["video_score"] > 0:
            scores["total_score"] = round(
                scores["lesson_plan_score"] * weights.get("lesson_plan", 0.4) +
                scores["video_score"] * weights.get("video", 0.6),
                1
            )
        elif scores["lesson_plan_score"] > 0:
            scores["total_score"] = scores["lesson_plan_score"]
        elif scores["video_score"] > 0:
            scores["total_score"] = scores["video_score"]
        
        return {k: round(v, 1) for k, v in scores.items()}
    
    def _calculate_speech_score(self, video_analysis: Dict) -> float:
        """从视频分析结果计算语音表达分数"""
        score = 100
        
        # 语速扣分
        speech_rate = video_analysis.get("speech_rate", 140)
        if speech_rate < 100 or speech_rate > 200:
            score -= 20
        elif speech_rate < 120 or speech_rate > 180:
            score -= 10
        
        # 停顿扣分
        pause_count = video_analysis.get("pause_count", 0)
        score -= min(pause_count * 5, 20)
        
        # 语气词扣分
        filler_count = video_analysis.get("filler_word_count", 0)
        score -= min(filler_count * 2, 15)
        
        return max(score, 0)
    
    async def _generate_ai_feedback(
        self,
        db: AsyncSession,
        student_id: int,
        lesson_plan_analysis: Optional[Dict],
        video_analysis: Optional[Dict],
        suggested_scores: Dict[str, float]
    ) -> str:
        """生成 AI 综合评语"""
        if not settings.AI_ENABLED:
            return self._generate_template_feedback(lesson_plan_analysis, video_analysis, suggested_scores)
        
        try:
            ai_service = get_dynamic_ai_service()
            
            # 构建 prompt
            prompt = self._build_feedback_prompt(
                lesson_plan_analysis, video_analysis, suggested_scores
            )
            
            response = await ai_service.chat_completion(
                db=db,
                messages=[{"role": "user", "content": prompt}],
                user_id=student_id,
                usage_type="grading",
                temperature=0.7
            )
            
            return response.strip()
            
        except Exception as e:
            # 降级到模板评语
            return self._generate_template_feedback(
                lesson_plan_analysis, video_analysis, suggested_scores
            )
    
    def _build_feedback_prompt(
        self,
        lesson_plan_analysis: Optional[Dict],
        video_analysis: Optional[Dict],
        suggested_scores: Dict[str, float]
    ) -> str:
        """构建评语生成 prompt"""
        parts = ["请根据以下分析结果，生成一段专业、具体、有建设性的试讲评语（150-250字）：\n"]
        
        if lesson_plan_analysis:
            parts.append(f"【教案分析】分数: {suggested_scores.get('lesson_plan_score', 0)}分")
            if "highlights" in lesson_plan_analysis:
                parts.append(f"亮点: {', '.join(lesson_plan_analysis['highlights'][:3])}")
            if "suggestions" in lesson_plan_analysis:
                parts.append(f"改进点: {', '.join(lesson_plan_analysis['suggestions'][:3])}")
        
        if video_analysis:
            parts.append(f"\n【视频分析】分数: {suggested_scores.get('video_score', 0)}分")
            parts.append(f"语速: {video_analysis.get('speech_rate', 0)} 字/分钟")
            parts.append(f"停顿: {video_analysis.get('pause_count', 0)} 次")
            parts.append(f"语气词: {video_analysis.get('filler_word_count', 0)} 次")
            
            gesture = video_analysis.get("gesture_analysis", {})
            if gesture:
                parts.append(f"姿态得分: {gesture.get('posture_score', 0)}")
                parts.append(f"手势得分: {gesture.get('gesture_score', 0)}")
        
        parts.append(f"\n【综合得分】{suggested_scores.get('total_score', 0)}分")
        parts.append("\n请生成评语，要求：1. 先肯定优点 2. 指出不足 3. 给出改进建议 4. 鼓励性收尾")
        
        return "\n".join(parts)
    
    def _generate_template_feedback(
        self,
        lesson_plan_analysis: Optional[Dict],
        video_analysis: Optional[Dict],
        suggested_scores: Dict[str, float]
    ) -> str:
        """生成模板评语（AI 不可用时的降级方案）"""
        total_score = suggested_scores.get("total_score", 0)
        
        if total_score >= 90:
            level = "优秀"
            comment = "整体表现非常出色，展现了扎实的教学基本功。"
        elif total_score >= 80:
            level = "良好"
            comment = "整体表现良好，具备较强的教学潜力。"
        elif total_score >= 70:
            level = "中等"
            comment = "基本达到要求，仍有较大提升空间。"
        elif total_score >= 60:
            level = "及格"
            comment = "勉强达到基本要求，需要加强练习。"
        else:
            level = "待提高"
            comment = "距离要求还有差距，请多加练习。"
        
        parts = [f"综合评定：{level}。{comment}"]
        
        if lesson_plan_analysis:
            lp_score = suggested_scores.get("lesson_plan_score", 0)
            if lp_score >= 85:
                parts.append("教案结构完整，内容充实。")
            elif lp_score >= 70:
                parts.append("教案基本规范，建议完善教学过程设计。")
            else:
                parts.append("教案需要进一步完善，注意结构和内容。")
        
        if video_analysis:
            speech_rate = video_analysis.get("speech_rate", 140)
            if 120 <= speech_rate <= 160:
                parts.append("语速适中。")
            elif speech_rate < 120:
                parts.append("语速偏慢，可适当加快。")
            else:
                parts.append("语速偏快，注意放慢节奏。")
            
            filler_count = video_analysis.get("filler_word_count", 0)
            if filler_count > 5:
                parts.append(f"注意减少语气词使用（{filler_count}次）。")
        
        parts.append("继续努力，相信你会越来越好！")
        
        return " ".join(parts)
    
    def _extract_highlights(
        self,
        lesson_plan_analysis: Optional[Dict],
        video_analysis: Optional[Dict]
    ) -> list:
        """提取亮点"""
        highlights = []
        
        if lesson_plan_analysis:
            lp_highlights = lesson_plan_analysis.get("highlights", [])
            highlights.extend(lp_highlights[:3])
        
        if video_analysis:
            # 从视频分析提取亮点
            if video_analysis.get("speech_rate", 0):
                rate = video_analysis["speech_rate"]
                if 120 <= rate <= 160:
                    highlights.append("语速控制良好")
            
            gesture = video_analysis.get("gesture_analysis", {})
            if gesture:
                if gesture.get("posture_score", 0) >= 80:
                    highlights.append("站姿端正自然")
                if gesture.get("gesture_score", 0) >= 80:
                    highlights.append("手势运用得当")
                if gesture.get("eye_contact_score", 0) >= 80:
                    highlights.append("眼神交流充分")
            
            suggestions = video_analysis.get("suggestions", [])
            for s in suggestions:
                if "好" in s or "优" in s or "充分" in s:
                    highlights.append(s)
        
        return highlights[:5]
    
    def _extract_improvements(
        self,
        lesson_plan_analysis: Optional[Dict],
        video_analysis: Optional[Dict]
    ) -> list:
        """提取改进建议"""
        improvements = []
        
        if lesson_plan_analysis:
            lp_suggestions = lesson_plan_analysis.get("suggestions", [])
            improvements.extend(lp_suggestions[:3])
        
        if video_analysis:
            video_suggestions = video_analysis.get("suggestions", [])
            improvements.extend(video_suggestions[:3])
            
            # 根据数据生成建议
            if video_analysis.get("filler_word_count", 0) > 5:
                improvements.append("减少语气词的使用，如'嗯'、'啊'、'那个'等")
            
            if video_analysis.get("pause_count", 0) > 3:
                improvements.append("减少不必要的停顿，保持表达的流畅性")
            
            speech_rate = video_analysis.get("speech_rate", 140)
            if speech_rate < 100:
                improvements.append("语速偏慢，建议适当加快，保持在120-160字/分钟")
            elif speech_rate > 180:
                improvements.append("语速偏快，建议适当放慢，让学生更好地理解")
        
        return improvements[:5]


# 全局服务实例
comprehensive_grading_service = ComprehensiveGradingService()
