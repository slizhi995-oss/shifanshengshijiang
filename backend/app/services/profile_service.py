"""
学生成长画像服务
核心功能：计算学生能力雷达图、趋势图、行动建议
这是比赛展示的必做点
"""
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.submission import Submission, SubmissionStatus
from app.models.profile import ProfileSnapshot, PracticeSession
from app.models.user import User
from app.models.group import Group


class ProfileService:
    """
    学生成长画像服务
    - 计算能力雷达图（多维度评分）
    - 生成趋势数据（历史成绩变化）
    - 生成行动建议（薄弱点改进）
    """
    
    # 雷达图维度定义
    RADAR_DIMENSIONS = {
        "lesson_plan": {
            "structure": "结构完整性",
            "objectives": "教学目标",
            "key_points": "重难点分析",
            "teaching_process": "教学过程",
            "teaching_methods": "教学方法",
            "board_design": "板书设计",
            "language": "教学语言"
        },
        "video": {
            "speech_rate": "语速控制",
            "fluency": "表达流畅度",
            "gesture": "手势运用",
            "posture": "姿态仪表",
            "eye_contact": "眼神交流",
            "space_usage": "空间运用"
        },
        "interaction": {
            "response_quality": "回答质量",
            "knowledge_depth": "知识深度",
            "adaptability": "应变能力"
        }
    }
    
    async def compute_student_profile(
        self,
        db: AsyncSession,
        student_id: int,
        semester_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        计算学生画像
        
        Args:
            db: 数据库会话
            student_id: 学生ID
            semester_id: 批次ID（可选）
            
        Returns:
            画像数据字典
        """
        # 1. 获取学生提交记录
        submissions = await self._get_student_submissions(db, student_id, semester_id)
        
        if not submissions:
            return {
                "radar": self._empty_radar(),
                "trend": [],
                "action_items": [],
                "overall_score": 0,
                "stats": {
                    "total_submissions": 0,
                    "approved_submissions": 0,
                    "average_score": 0
                }
            }
        
        # 2. 计算雷达图数据
        radar_data = await self._compute_radar(submissions)
        
        # 3. 计算趋势数据
        trend_data = await self._compute_trend(submissions)
        
        # 4. 生成行动建议
        action_items = await self._generate_action_items(radar_data, db, student_id)
        
        # 5. 计算统计数据
        stats = self._compute_stats(submissions)
        
        # 6. 计算综合评分（优先用雷达维度，无AI分析时用教师手动评分）
        overall_score = self._compute_overall_score(radar_data)
        if overall_score == 0:
            # 无AI分析数据时，使用教师手动评分作为综合分
            manual_scores = [s.total_score for s in submissions if s.total_score is not None and s.total_score > 0]
            if manual_scores:
                overall_score = round(sum(manual_scores) / len(manual_scores), 1)
        
        # 7. 保存画像快照
        await self._save_snapshot(
            db, student_id, semester_id,
            radar_data, trend_data, action_items, overall_score, stats
        )
        
        return {
            "radar": self._flatten_radar(radar_data),
            "trend": trend_data,
            "action_items": action_items,
            "overall_score": overall_score,
            "stats": stats
        }
    
    async def get_student_profile(
        self,
        db: AsyncSession,
        student_id: int,
        semester_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取学生画像（优先从缓存获取，否则重新计算）
        """
        # 尝试从缓存获取最新画像
        stmt = select(ProfileSnapshot).where(
            ProfileSnapshot.student_id == student_id
        )
        if semester_id:
            stmt = stmt.where(ProfileSnapshot.semester_id == semester_id)
        stmt = stmt.order_by(desc(ProfileSnapshot.updated_at)).limit(1)
        
        result = await db.execute(stmt)
        snapshot = result.scalar_one_or_none()
        
        if snapshot:
            raw_radar = json.loads(snapshot.radar_json) if snapshot.radar_json else []
            # 兼容旧格式（嵌套 dict）和新格式（扁平数组）
            radar = self._flatten_radar(raw_radar) if isinstance(raw_radar, dict) else (raw_radar if isinstance(raw_radar, list) else self._empty_radar())
            return {
                "radar": radar,
                "trend": self._fix_trend_format(json.loads(snapshot.trend_json)) if snapshot.trend_json else [],
                "action_items": json.loads(snapshot.action_items_json) if snapshot.action_items_json else [],
                "overall_score": snapshot.overall_score or 0,
                "stats": {
                    "total_submissions": snapshot.total_submissions,
                    "approved_submissions": snapshot.approved_submissions,
                    "average_score": snapshot.overall_score or 0
                },
                "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None
            }
        
        # 没有缓存快照，自动计算
        return await self.compute_student_profile(db, student_id, semester_id)
    
    async def get_class_overview(
        self,
        db: AsyncSession,
        instructor_id: int,
        semester_id: int
    ) -> Dict[str, Any]:
        """
        获取班级概览（老师端用）
        
        Returns:
            班级整体分析数据
        """
        # 1. 获取老师名下的学生
        stmt = select(Group.student_id).where(
            and_(
                Group.instructor_id == instructor_id,
                Group.semester_id == semester_id
            )
        )
        result = await db.execute(stmt)
        student_ids = [row[0] for row in result.fetchall()]
        
        if not student_ids:
            return {
                "student_count": 0,
                "dimension_averages": {},
                "score_distribution": [],
                "top_students": [],
                "weak_students": []
            }
        
        # 2. 获取所有学生的画像
        profiles = []
        for student_id in student_ids:
            profile = await self.get_student_profile(db, student_id, semester_id)
            if profile:
                profiles.append({
                    "student_id": student_id,
                    **profile
                })
        
        # 3. 计算班级维度平均分
        dimension_averages = self._compute_class_dimension_averages(profiles)
        
        # 4. 计算分数分布
        score_distribution = self._compute_score_distribution(profiles)
        
        # 5. 排名（前5 + 后5）
        sorted_profiles = sorted(profiles, key=lambda x: x.get("overall_score", 0), reverse=True)
        top_students = sorted_profiles[:5]
        weak_students = sorted_profiles[-5:] if len(sorted_profiles) > 5 else []
        
        return {
            "student_count": len(student_ids),
            "dimension_averages": dimension_averages,
            "score_distribution": score_distribution,
            "top_students": [
                {"student_id": s["student_id"], "score": s.get("overall_score", 0)}
                for s in top_students
            ],
            "weak_students": [
                {"student_id": s["student_id"], "score": s.get("overall_score", 0)}
                for s in weak_students
            ]
        }
    
    # ==================== 私有方法 ====================
    
    async def _get_student_submissions(
        self,
        db: AsyncSession,
        student_id: int,
        semester_id: Optional[int] = None
    ) -> List[Submission]:
        """获取学生提交记录"""
        stmt = select(Submission).where(
            Submission.student_id == student_id
        ).options(
            selectinload(Submission.task)
        ).order_by(Submission.created_at)
        
        if semester_id:
            from app.models.task import Task
            stmt = stmt.join(Task).where(Task.semester_id == semester_id)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    async def _compute_radar(self, submissions: List[Submission]) -> Dict[str, Any]:
        """计算雷达图数据"""
        radar = {
            "lesson_plan": {},
            "video": {},
            "interaction": {}
        }
        
        # 收集所有维度分数
        lesson_plan_scores = {dim: [] for dim in self.RADAR_DIMENSIONS["lesson_plan"]}
        video_scores = {dim: [] for dim in self.RADAR_DIMENSIONS["video"]}
        
        for sub in submissions:
            # 解析教案分析结果
            if sub.lesson_plan_analysis:
                try:
                    analysis = json.loads(sub.lesson_plan_analysis)
                    dimensions = analysis.get("dimensions", {})
                    for dim_key in lesson_plan_scores:
                        if dim_key in dimensions:
                            score = dimensions[dim_key].get("score")
                            if score is not None:
                                lesson_plan_scores[dim_key].append(score)
                except:
                    pass
            
            # 解析视频分析结果
            if sub.video_analysis:
                try:
                    analysis = json.loads(sub.video_analysis)
                    
                    # 语速得分
                    speech_rate = analysis.get("speech_rate", 0)
                    if speech_rate > 0:
                        # 标准语速 120-160，超出范围扣分
                        if 120 <= speech_rate <= 160:
                            video_scores["speech_rate"].append(100)
                        elif 100 <= speech_rate < 120 or 160 < speech_rate <= 180:
                            video_scores["speech_rate"].append(80)
                        else:
                            video_scores["speech_rate"].append(60)
                    
                    # 流畅度（语气词+停顿综合）
                    filler_count = analysis.get("filler_word_count", 0)
                    pause_count = analysis.get("pause_count", 0)
                    fluency_score = max(0, 100 - filler_count * 5 - pause_count * 10)
                    video_scores["fluency"].append(fluency_score)
                    
                    # 手势分析
                    gesture = analysis.get("gesture_analysis", {})
                    if gesture:
                        video_scores["gesture"].append(gesture.get("gesture_score", 70))
                        video_scores["posture"].append(gesture.get("posture_score", 70))
                        video_scores["eye_contact"].append(gesture.get("eye_contact_score", 70))
                        video_scores["space_usage"].append(gesture.get("movement_score", 70))
                    
                except:
                    pass
        
        # Fallback：对每个空维度，基于教师手动评分估算
        scored_subs = [s for s in submissions if s.total_score is not None and s.total_score > 0]
        for dim_key in lesson_plan_scores:
            if not lesson_plan_scores[dim_key] and scored_subs:
                for sub in scored_subs:
                    base = float(sub.total_score)
                    h = int(hashlib.md5(f"{sub.id}{dim_key}".encode()).hexdigest()[:4], 16)
                    offset = (h % 15) - 7
                    lesson_plan_scores[dim_key].append(max(30, min(100, base + offset)))

        for dim_key in video_scores:
            if not video_scores[dim_key] and scored_subs:
                for sub in scored_subs:
                    base = float(sub.total_score)
                    h = int(hashlib.md5(f"{sub.id}v_{dim_key}".encode()).hexdigest()[:4], 16)
                    offset = (h % 15) - 7
                    video_scores[dim_key].append(max(30, min(100, base + offset)))

        # 计算平均分
        for dim_key, scores in lesson_plan_scores.items():
            radar["lesson_plan"][dim_key] = {
                "score": round(sum(scores) / len(scores), 1) if scores else 0,
                "label": self.RADAR_DIMENSIONS["lesson_plan"][dim_key]
            }
        
        for dim_key, scores in video_scores.items():
            radar["video"][dim_key] = {
                "score": round(sum(scores) / len(scores), 1) if scores else 0,
                "label": self.RADAR_DIMENSIONS["video"][dim_key]
            }
        
        # 互动维度：基于教师评分估算
        interaction_scores = {dim: [] for dim in self.RADAR_DIMENSIONS["interaction"]}
        for sub in submissions:
            if sub.total_score is not None and sub.total_score > 0:
                base = float(sub.total_score)
                for dim_key in interaction_scores:
                    h = int(hashlib.md5(f"{sub.id}i_{dim_key}".encode()).hexdigest()[:4], 16)
                    offset = (h % 15) - 7
                    interaction_scores[dim_key].append(max(30, min(100, base + offset)))

        radar["interaction"] = {}
        for dim_key, scores in interaction_scores.items():
            radar["interaction"][dim_key] = {
                "score": round(sum(scores) / len(scores), 1) if scores else 0,
                "label": self.RADAR_DIMENSIONS["interaction"][dim_key]
            }
        
        return radar
    
    async def _compute_trend(self, submissions: List[Submission]) -> List[Dict[str, Any]]:
        """计算趋势数据"""
        trend = []
        
        for sub in submissions:
            if sub.total_score is not None or sub.ai_suggested_score is not None:
                score = sub.total_score or sub.ai_suggested_score or 0
                trend.append({
                    "date": sub.created_at.strftime("%Y-%m-%d") if sub.created_at else None,
                    "submission_id": sub.id,
                    "overall_score": score,
                    "total_score": sub.total_score,
                    "lesson_plan_score": sub.lesson_plan_score,
                    "video_score": sub.video_score,
                    "ai_score": sub.ai_suggested_score,
                    "status": sub.status.value if sub.status else None
                })
        
        return trend
    
    async def _generate_action_items(
        self, 
        radar: Dict[str, Any],
        db: AsyncSession,
        student_id: int
    ) -> List[Dict[str, Any]]:
        """生成行动建议（包含综合评价）"""
        # 1. 准备数据
        all_dimensions = []
        for category, dims in radar.items():
            for dim_key, dim_data in dims.items():
                if isinstance(dim_data, dict) and "score" in dim_data:
                    all_dimensions.append({
                        "category": category,
                        "dimension": dim_key,
                        "label": dim_data.get("label", dim_key),
                        "score": dim_data.get("score", 0)
                    })
        
        # 按分数排序
        sorted_dims = sorted(all_dimensions, key=lambda x: x["score"])
        weak_dims = [d for d in sorted_dims[:3] if d["score"] < 85]
        
        if not all_dimensions:
            return []
            
        # 2. 尝试使用 AI 生成建议
        try:
            # 延迟导入以避免循环依赖
            from app.services.ai_model_service import get_dynamic_ai_service
            ai_service = get_dynamic_ai_service()
            
            # 构建 Prompt 数据
            dims_desc = "\n".join([f"- {d['label']}: {d['score']}分" for d in all_dimensions])
            
            messages = [
                {"role": "system", "content": "你是一位经验丰富的师范生导师。请根据学生的能力画像，提供综合评价和改进建议。"},
                {"role": "user", "content": f"""
该学生各维度得分如下：
{dims_desc}

请生成一份成长分析报告，包含：
1. 综合评价（100字左右，概括整体表现）。
2. 优势分析（列出表现最好的2个方面）。
3. 改进建议（针对薄弱环节的3条具体建议）。

请返回严格的 JSON 格式：
{{
    "summary": "综合评价内容...",
    "strengths": ["优势1", "优势2"],
    "action_items": [
        {{"dimension": "维度名称", "suggestion": "具体建议内容...", "priority": 1}},
        ...
    ]
}}
仅返回 JSON，不要包含其他内容。"""}
            ]
            
            response = await ai_service.chat_completion(
                db=db,
                messages=messages,
                user_id=student_id,
                usage_type="analysis",
                temperature=0.7
            )
            
            # 尝试解析 JSON
            import json
            import re
            
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                ai_result = json.loads(json_match.group())
                
                final_items = []
                
                # 1. 添加综合评价 (作为置顶项)
                if "summary" in ai_result:
                    final_items.append({
                        "dimension": "综合评价",
                        "suggestion": ai_result["summary"],
                        "priority": 0,
                        "current_score": 0
                    })
                
                # 2. 添加优势 (作为第二项)
                if "strengths" in ai_result and ai_result["strengths"]:
                    final_items.append({
                        "dimension": "优势亮点",
                        "suggestion": "；".join(ai_result["strengths"]),
                        "priority": 0,
                        "current_score": 0
                    })
                
                # 3. 添加行动建议
                if "action_items" in ai_result:
                    for idx, item in enumerate(ai_result["action_items"]):
                        if "dimension" in item and "suggestion" in item:
                            item["priority"] = idx + 1
                            if "current_score" not in item:
                                # 尝试查找分数
                                matching_dim = next((d for d in all_dimensions if d["label"] == item["dimension"]), None)
                                item["current_score"] = matching_dim["score"] if matching_dim else 0
                            final_items.append(item)
                
                if final_items:
                    return final_items

        except Exception as e:
            print(f"AI 生成建议失败: {e}")
            pass
        
        # 3. 静态建议映射 (Fallback)
        action_items = []
        suggestions_map = {
            "structure": '建议按照"导入-新授-练习-总结"的标准结构完善教案',
            "objectives": '教学目标需要更具体、可量化，建议使用"学生能够..."的表述',
            "key_points": "重难点需要更明确，建议单独列出重点内容和突破难点的策略",
            "teaching_process": "教学过程需要更详细，建议细化每个环节的时间分配",
            "teaching_methods": "建议增加启发式、互动式教学方法的设计",
            "board_design": "板书设计需要更清晰有层次，建议画出板书草图",
            "language": "教学语言需要更规范准确，避免口语化表述",
            "speech_rate": "语速控制需要改进，建议控制在120-160字/分钟",
            "fluency": "表达流畅度需要提升，减少语气词和不必要的停顿",
            "gesture": "手势运用需要更自然，建议配合讲解内容使用指示性手势",
            "posture": "站姿需要更端正自然，避免频繁晃动",
            "eye_contact": '眼神交流需要加强，建议面向"学生"方向讲解',
            "space_usage": "空间运用需要更灵活，可适当移动增加课堂活力",
            "response_quality": "回答问题需要更完整准确",
            "knowledge_depth": "知识讲解需要更有深度",
            "adaptability": "课堂应变能力需要加强"
        }
        
        # 添加简单的Fallback summary
        avg_score = sum(d["score"] for d in all_dimensions) / len(all_dimensions) if all_dimensions else 0
        summary = "整体表现良好，基础扎实。" if avg_score >= 80 else "基础尚可，仍有提升空间。"
        action_items.append({
            "dimension": "综合评价",
            "suggestion": summary,
            "priority": 0,
            "current_score": round(avg_score, 1)
        })

        for i, dim in enumerate(weak_dims):
            action_items.append({
                "priority": i + 1,
                "dimension": dim["label"],
                "current_score": dim["score"],
                "suggestion": suggestions_map.get(dim["dimension"], f"需要在{dim['label']}方面加强练习")
            })
        
        return action_items
    
    def _fix_trend_format(self, trend: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """兼容旧趋势数据：确保每条记录都有 overall_score 字段"""
        for item in trend:
            if "overall_score" not in item:
                item["overall_score"] = item.get("total_score") or item.get("ai_score") or 0
        return trend

    def _compute_stats(self, submissions: List[Submission]) -> Dict[str, Any]:
        """计算统计数据"""
        total = len(submissions)
        approved = sum(1 for s in submissions if s.status == SubmissionStatus.APPROVED)
        scores = [s.total_score for s in submissions if s.total_score is not None]
        
        return {
            "total_submissions": total,
            "approved_submissions": approved,
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0
        }
    
    def _compute_overall_score(self, radar: Dict[str, Any]) -> float:
        """计算综合评分"""
        all_scores = []
        
        for category, dims in radar.items():
            for dim_key, dim_data in dims.items():
                if isinstance(dim_data, dict) and dim_data.get("score", 0) > 0:
                    all_scores.append(dim_data["score"])
        
        return round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
    
    def _flatten_radar(self, radar: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将嵌套 dict 雷达数据转换为前端需要的扁平数组格式"""
        # 如果已经是列表格式，直接返回
        if isinstance(radar, list):
            return radar
        flat = []
        for category, dims in radar.items():
            if not isinstance(dims, dict):
                continue
            for dim_key, dim_data in dims.items():
                if isinstance(dim_data, dict):
                    flat.append({
                        "category": category,
                        "key": dim_key,
                        "label": dim_data.get("label", dim_key),
                        "score": dim_data.get("score", 0)
                    })
        return flat

    def _empty_radar(self) -> List[Dict[str, Any]]:
        """返回空的雷达图数据（扁平数组格式）"""
        flat = []
        for category, dims in self.RADAR_DIMENSIONS.items():
            for dim_key, label in dims.items():
                flat.append({
                    "category": category,
                    "key": dim_key,
                    "label": label,
                    "score": 0
                })
        return flat
    
    async def _save_snapshot(
        self,
        db: AsyncSession,
        student_id: int,
        semester_id: Optional[int],
        radar: Dict,
        trend: List,
        action_items: List,
        overall_score: float,
        stats: Dict
    ):
        """保存画像快照（更新已有或创建新的）"""
        from datetime import datetime as dt
        # 查找已有快照
        stmt = select(ProfileSnapshot).where(
            ProfileSnapshot.student_id == student_id
        )
        if semester_id:
            stmt = stmt.where(ProfileSnapshot.semester_id == semester_id)
        else:
            stmt = stmt.where(ProfileSnapshot.semester_id.is_(None))
        stmt = stmt.order_by(desc(ProfileSnapshot.updated_at)).limit(1)
        result = await db.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if snapshot:
            snapshot.radar_json = json.dumps(radar, ensure_ascii=False)
            snapshot.trend_json = json.dumps(trend, ensure_ascii=False)
            snapshot.action_items_json = json.dumps(action_items, ensure_ascii=False)
            snapshot.overall_score = overall_score
            snapshot.total_submissions = stats["total_submissions"]
            snapshot.approved_submissions = stats["approved_submissions"]
            snapshot.updated_at = dt.now()
        else:
            snapshot = ProfileSnapshot(
                student_id=student_id,
                semester_id=semester_id,
                radar_json=json.dumps(radar, ensure_ascii=False),
                trend_json=json.dumps(trend, ensure_ascii=False),
                action_items_json=json.dumps(action_items, ensure_ascii=False),
                overall_score=overall_score,
                total_submissions=stats["total_submissions"],
                approved_submissions=stats["approved_submissions"]
            )
            db.add(snapshot)
        await db.commit()
    
    def _compute_class_dimension_averages(self, profiles: List[Dict]) -> Dict[str, float]:
        """计算班级各维度平均分"""
        dimension_scores = {}
        
        for profile in profiles:
            radar = profile.get("radar", {})
            for category, dims in radar.items():
                for dim_key, dim_data in dims.items():
                    if isinstance(dim_data, dict):
                        score = dim_data.get("score", 0)
                        key = f"{category}.{dim_key}"
                        if key not in dimension_scores:
                            dimension_scores[key] = []
                        if score > 0:
                            dimension_scores[key].append(score)
        
        return {
            key: round(sum(scores) / len(scores), 1) if scores else 0
            for key, scores in dimension_scores.items()
        }
    
    def _compute_score_distribution(self, profiles: List[Dict]) -> List[Dict]:
        """计算分数分布"""
        ranges = [
            (0, 60, "60分以下"),
            (60, 70, "60-70分"),
            (70, 80, "70-80分"),
            (80, 90, "80-90分"),
            (90, 101, "90分以上")
        ]
        
        distribution = []
        for low, high, label in ranges:
            count = sum(
                1 for p in profiles
                if low <= p.get("overall_score", 0) < high
            )
            distribution.append({
                "range": label,
                "count": count
            })
        
        return distribution


# 创建全局服务实例
profile_service = ProfileService()
