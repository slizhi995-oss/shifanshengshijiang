"""
视频分析服务
支持语音识别、语速分析、停顿检测、语气词统计、云端视觉分析等功能
"""
import os
import re
import json
import asyncio
import base64
import shutil
from typing import Dict, Any, List, Optional, Tuple

from app.core.config import settings
from app.services.model_api import chat_completion
from app.services.media_tools import ffmpeg_executable, run_media_tool


class VideoAnalysisService:
    """视频分析服务类"""
    
    def __init__(self):
        """初始化视频分析服务"""
        self.provider = settings.AI_PROVIDER.lower()
        # Token 使用量追踪
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "audio_seconds": 0,
            "video_frames": 0,  # 分析的视频帧数
        }
        # 缓存从数据库读取的配置
        self._db_configs_cache: Optional[Dict[str, Any]] = None
    
    async def _get_db_config(self, model_type: str) -> Optional[Dict[str, Any]]:
        """
        从数据库获取指定类型的默认模型配置。
        优先使用数据库配置，如果没有则回退到 env。
        """
        try:
            from app.core.database import async_session_factory
            from app.models.ai_config import AIModelConfig
            from sqlalchemy import select, and_

            async with async_session_factory() as session:
                result = await session.execute(
                    select(AIModelConfig).where(
                        and_(
                            AIModelConfig.model_type == model_type,
                            AIModelConfig.is_enabled == True,
                            AIModelConfig.is_default == True,
                        )
                    )
                )
                config = result.scalar_one_or_none()
                if not config:
                    # 没有默认的，取优先级最高的
                    result = await session.execute(
                        select(AIModelConfig).where(
                            and_(
                                AIModelConfig.model_type == model_type,
                                AIModelConfig.is_enabled == True,
                            )
                        ).order_by(AIModelConfig.priority.asc()).limit(1)
                    )
                    config = result.scalar_one_or_none()

                if config:
                    return {
                        "api_key": config.api_key,
                        "model_id": config.model_id,
                        "api_base_url": config.api_base_url,
                        "provider": config.provider,
                    }
        except Exception as e:
            print(f"⚠️ 从数据库读取 {model_type} 模型配置失败: {e}")
        return None

    async def _get_api_key(self) -> str:
        """获取 API Key，优先从数据库读取"""
        cfg = await self._get_db_config("text")
        if cfg and cfg.get("api_key"):
            return cfg["api_key"]
        return settings.DASHSCOPE_API_KEY

    async def _get_vision_config(self) -> Tuple[str, str]:
        """获取视觉模型配置 (api_key, model_id)"""
        cfg = await self._get_db_config("vision")
        if cfg and cfg.get("api_key"):
            return cfg["api_key"], cfg.get("model_id", "qwen-vl-max")
        return settings.DASHSCOPE_API_KEY, getattr(settings, 'DASHSCOPE_VISION_MODEL', 'qwen-vl-max')

    async def _get_audio_config(self) -> Tuple[str, str]:
        """获取音频模型配置 (api_key, model_id)"""
        cfg = await self._get_db_config("audio")
        if cfg and cfg.get("api_key"):
            return cfg["api_key"], cfg.get("model_id", "qwen-omni-turbo")
        return settings.DASHSCOPE_API_KEY, getattr(settings, 'DASHSCOPE_AUDIO_MODEL', 'qwen-omni-turbo')

    async def _get_multimodal_config(self, model_type: str) -> Dict[str, Any]:
        """Use the administrator's model, credentials and regional endpoint together."""
        config = await self._get_db_config(model_type)
        if not config:
            config = {
                "provider": "dashscope",
                "api_key": settings.DASHSCOPE_API_KEY,
                "api_base_url": settings.DASHSCOPE_BASE_URL,
                "model_id": settings.DASHSCOPE_AUDIO_MODEL if model_type == "audio" else settings.DASHSCOPE_VISION_MODEL,
            }
        return {**config, "model_type": model_type}
    
    def _reset_token_usage(self):
        """重置 token 使用量"""
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "audio_seconds": 0,
            "video_frames": 0,
        }
    
    def _add_token_usage(self, input_tokens: int = 0, output_tokens: int = 0, 
                         audio_seconds: float = 0, video_frames: int = 0):
        """累加 token 使用量"""
        self.token_usage["input_tokens"] += input_tokens
        self.token_usage["output_tokens"] += output_tokens
        self.token_usage["total_tokens"] += input_tokens + output_tokens
        self.token_usage["audio_seconds"] += audio_seconds
        self.token_usage["video_frames"] += video_frames
        
    # ==================== 主分析入口 ====================
    
    async def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """
        分析视频（主入口）
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            分析结果字典
        """
        # 重置 token 使用量
        self._reset_token_usage()
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        # 获取视频时长
        duration = await self._get_video_duration(video_path)
        
        # 语音识别（转文字）
        print("🎤 开始语音识别...")
        transcript_result = await self._speech_to_text(video_path)
        
        # 分析文字内容
        text_analysis = self._analyze_text(
            transcript_result["text"],
            transcript_result.get("segments", []),
            duration
        )
        
        # 视觉分析（云端 AI 或本地 MediaPipe）
        visual_analysis = {}
        if settings.ENABLE_GESTURE_ANALYSIS:
            try:
                if getattr(settings, 'USE_CLOUD_VISION', True):
                    # 使用云端视觉模型分析
                    print("🎬 开始云端视觉分析...")
                    visual_analysis = await self._cloud_vision_analysis(video_path, duration)
                else:
                    # 使用本地 MediaPipe 分析
                    print("🎬 开始本地动作分析...")
                    visual_analysis = await self._analyze_gestures_local(video_path)
            except Exception as e:
                print(f"视觉分析失败: {e}")
                visual_analysis = {"error": str(e)}
        
        # 综合评分
        overall_score = self._calculate_overall_score(text_analysis, visual_analysis)
        
        # 记录音频时长用于计费参考
        self._add_token_usage(audio_seconds=duration)
        
        # 合并建议
        suggestions = self._generate_suggestions(text_analysis, visual_analysis)
        if visual_analysis.get("ai_suggestions"):
            suggestions = visual_analysis["ai_suggestions"] + suggestions
        
        return {
            "duration": duration,
            "transcript": transcript_result["text"],
            "segments": transcript_result.get("segments", []),
            "speech_rate": text_analysis["speech_rate"],
            "pause_count": text_analysis["pause_count"],
            "filler_word_count": text_analysis["filler_word_count"],
            "filler_words": text_analysis["filler_words"],
            "time_distribution": text_analysis.get("time_distribution", {}),
            "gesture_analysis": visual_analysis,
            "overall_score": overall_score,
            "suggestions": suggestions,
            "token_usage": self.token_usage.copy(),
        }
    
    # ==================== 云端视觉分析 ====================
    
    async def _cloud_vision_analysis(self, video_path: str, duration: float) -> Dict[str, Any]:
        """
        使用通义千问视觉模型分析视频
        
        Args:
            video_path: 视频文件路径
            duration: 视频时长
            
        Returns:
            视觉分析结果
        """
        # 提取关键帧
        frames = await self._extract_key_frames(video_path, duration)
        if not frames:
            return {"error": "无法提取视频帧"}
        
        self._add_token_usage(video_frames=len(frames))
        
        # 将帧转为 base64
        frame_images = []
        for frame_path in frames:
            with open(frame_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
                frame_images.append(f"data:image/jpeg;base64,{img_base64}")
            # 清理临时文件
            os.remove(frame_path)
        
        # 调用视觉模型分析
        analysis_result = await self._call_vision_model(frame_images)
        
        return analysis_result
    
    async def _extract_key_frames(self, video_path: str, duration: float, 
                                   max_frames: int = 8) -> List[str]:
        """
        从视频中提取关键帧
        
        Args:
            video_path: 视频文件路径
            duration: 视频时长
            max_frames: 最大帧数（控制成本）
            
        Returns:
            帧图片路径列表
        """
        # 计算采样间隔
        interval = max(duration / max_frames, 5)  # 至少每5秒一帧
        
        frames = []
        output_dir = os.path.dirname(video_path)
        base_name = os.path.basename(video_path).rsplit(".", 1)[0]
        
        for i in range(min(max_frames, int(duration / interval) + 1)):
            timestamp = i * interval
            if timestamp >= duration:
                break
                
            output_path = os.path.join(output_dir, f"{base_name}_frame_{i}.jpg")
            
            cmd = [
                ffmpeg_executable(),
                "-ss", str(timestamp),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                output_path
            ]
            
            await run_media_tool(cmd, timeout=60)
            
            if os.path.exists(output_path):
                frames.append(output_path)
        
        return frames
    
    async def _call_vision_model(self, frame_images: List[str]) -> Dict[str, Any]:
        """
        调用通义千问视觉模型分析图片
        
        Args:
            frame_images: base64 编码的图片列表
            
        Returns:
            分析结果
        """
        config = await self._get_multimodal_config("vision")
        
        # 构建消息内容
        content = []
        for img in frame_images:
            content.append({"type": "image_url", "image_url": {"url": img}})
        
        content.append({
            "type": "text",
            "text": """请分析这些教学视频截图中教师的表现，从以下维度进行评分和分析：

1. **姿态仪表** (0-100分)
   - 站姿是否端正自然
   - 着装是否得体专业
   - 整体精神面貌

2. **手势运用** (0-100分)
   - 手势是否自然协调
   - 是否有效辅助讲解
   - 手势幅度是否适中

3. **眼神交流** (0-100分)
   - 是否面向学生/镜头
   - 眼神是否自信从容
   - 是否有环顾全场

4. **表情管理** (0-100分)
   - 表情是否亲切自然
   - 是否有适当的微笑
   - 是否展现教学热情

5. **空间运用** (0-100分)
   - 是否有适当走动
   - 与讲台/黑板的配合
   - 教学区域的利用

6. **教具使用** (0-100分，如果有的话)
   - PPT/板书是否清晰
   - 教具使用是否熟练
   - 多媒体配合效果

请以 JSON 格式返回分析结果，格式如下：
{
    "posture_score": 85,
    "posture_comment": "站姿端正，精神饱满",
    "gesture_score": 80,
    "gesture_comment": "手势自然，能配合讲解",
    "eye_contact_score": 75,
    "eye_contact_comment": "基本面向镜头，偶有低头",
    "expression_score": 82,
    "expression_comment": "表情亲切，有教学热情",
    "movement_score": 78,
    "movement_comment": "有适当走动，空间利用合理",
    "teaching_aids_score": 85,
    "teaching_aids_comment": "PPT清晰，切换流畅",
    "overall_gesture_score": 81,
    "highlights": ["站姿端正", "表情亲切"],
    "improvements": ["可以增加与学生的眼神交流", "手势可以更加丰富"],
    "ai_suggestions": ["建议在讲解重点时配合适当的手势强调", "可以尝试在教室中适当走动增加互动感"]
}

只返回 JSON，不要其他内容。"""
        })
        
        try:
            result = await chat_completion(
                config, [{"role": "user", "content": content}],
                stream="omni" in config["model_id"].lower(),
            )
            
            # 提取 token 使用量
            if "usage" in result:
                usage = result["usage"]
                self._add_token_usage(
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0)
                )
            
            # 解析响应
            text = result["text"]
            
            # 解析 JSON 结果
            if text:
                # 尝试提取 JSON
                json_match = re.search(r'\{[\s\S]*\}', text)
                if json_match:
                    analysis = json.loads(json_match.group())
                    return analysis
            
            return {"error": "无法解析视觉分析结果", "raw": text}
            
        except Exception as e:
            print(f"视觉模型调用失败: {e}")
            return {"error": str(e)}
    
    # ==================== 本地动作分析 (MediaPipe) ====================
    
    async def _analyze_gestures_local(self, video_path: str) -> Dict[str, Any]:
        """
        使用本地 MediaPipe 分析动作（备用方案）
        """
        try:
            import cv2
            import mediapipe as mp
        except ImportError:
            return {"error": "未安装 mediapipe，请运行: pip install mediapipe opencv-python"}
        
        mp_pose = mp.solutions.pose
        mp_face_mesh = mp.solutions.face_mesh
        
        pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        cap = cv2.VideoCapture(video_path)
        
        frame_count = 0
        posture_scores = []
        gesture_scores = []
        eye_contact_scores = []
        
        prev_landmarks = None
        movement_amounts = []
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        sample_interval = int(fps) if fps > 0 else 30
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            if frame_count % sample_interval != 0:
                continue
            
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            pose_results = pose.process(image)
            if pose_results.pose_landmarks:
                posture_score = self._evaluate_posture(pose_results.pose_landmarks)
                posture_scores.append(posture_score)
                
                gesture_score = self._evaluate_gestures(pose_results.pose_landmarks)
                gesture_scores.append(gesture_score)
                
                if prev_landmarks:
                    movement = self._calculate_movement(prev_landmarks, pose_results.pose_landmarks)
                    movement_amounts.append(movement)
                prev_landmarks = pose_results.pose_landmarks
            
            face_results = face_mesh.process(image)
            if face_results.multi_face_landmarks:
                eye_score = self._evaluate_eye_contact(face_results.multi_face_landmarks[0])
                eye_contact_scores.append(eye_score)
        
        cap.release()
        pose.close()
        face_mesh.close()
        
        if not posture_scores:
            return {"error": "未检测到人物"}
        
        if movement_amounts:
            avg_movement = sum(movement_amounts) / len(movement_amounts)
            if 0.01 <= avg_movement <= 0.05:
                movement_score = 90
            elif avg_movement < 0.01:
                movement_score = 70
            else:
                movement_score = 75
        else:
            movement_score = 80
        
        avg_posture = round(sum(posture_scores) / len(posture_scores), 1)
        avg_gesture = round(sum(gesture_scores) / len(gesture_scores), 1)
        avg_eye_contact = round(sum(eye_contact_scores) / len(eye_contact_scores), 1) if eye_contact_scores else 80
        
        overall_gesture_score = round(
            avg_posture * 0.3 + avg_gesture * 0.3 + avg_eye_contact * 0.2 + movement_score * 0.2,
            1
        )
        
        gesture_suggestions = self._generate_gesture_suggestions(
            avg_posture, avg_gesture, avg_eye_contact, movement_score
        )
        
        return {
            "posture_score": avg_posture,
            "gesture_score": avg_gesture,
            "eye_contact_score": avg_eye_contact,
            "movement_score": round(movement_score, 1),
            "overall_gesture_score": overall_gesture_score,
            "frame_analyzed": len(posture_scores),
            "gesture_suggestions": gesture_suggestions,
            "analysis_method": "local_mediapipe",
        }
    
    def _evaluate_posture(self, landmarks) -> float:
        """评估姿态"""
        score = 100
        
        left_shoulder = landmarks.landmark[11]
        right_shoulder = landmarks.landmark[12]
        shoulder_diff = abs(left_shoulder.y - right_shoulder.y)
        score -= shoulder_diff * 300
        
        nose = landmarks.landmark[0]
        left_hip = landmarks.landmark[23]
        right_hip = landmarks.landmark[24]
        hip_center_x = (left_hip.x + right_hip.x) / 2
        body_lean = abs(nose.x - hip_center_x)
        score -= body_lean * 200
        
        left_ear = landmarks.landmark[7]
        right_ear = landmarks.landmark[8]
        head_tilt = abs(left_ear.y - right_ear.y)
        score -= head_tilt * 200
        
        return max(0, min(100, score))
    
    def _evaluate_gestures(self, landmarks) -> float:
        """评估手势"""
        score = 80
        
        left_wrist = landmarks.landmark[15]
        right_wrist = landmarks.landmark[16]
        left_shoulder = landmarks.landmark[11]
        right_shoulder = landmarks.landmark[12]
        
        left_hand_height = left_shoulder.y - left_wrist.y
        right_hand_height = right_shoulder.y - right_wrist.y
        
        if -0.3 < left_hand_height < 0.3:
            score += 5
        if -0.3 < right_hand_height < 0.3:
            score += 5
        
        left_hand_spread = abs(left_wrist.x - left_shoulder.x)
        right_hand_spread = abs(right_wrist.x - right_shoulder.x)
        
        if left_hand_spread > 0.1:
            score += 5
        if right_hand_spread > 0.1:
            score += 5
        
        return max(0, min(100, score))
    
    def _evaluate_eye_contact(self, face_landmarks) -> float:
        """评估眼神接触"""
        score = 80
        nose_tip = face_landmarks.landmark[1]
        face_direction = abs(nose_tip.x - 0.5)
        
        if face_direction < 0.1:
            score = 95
        elif face_direction < 0.2:
            score = 85
        else:
            score = 70
        
        return score
    
    def _calculate_movement(self, prev_landmarks, curr_landmarks) -> float:
        """计算移动量"""
        total_movement = 0
        key_points = [0, 11, 12, 15, 16]
        
        for idx in key_points:
            prev = prev_landmarks.landmark[idx]
            curr = curr_landmarks.landmark[idx]
            movement = ((curr.x - prev.x) ** 2 + (curr.y - prev.y) ** 2) ** 0.5
            total_movement += movement
        
        return total_movement / len(key_points)
    
    def _generate_gesture_suggestions(self, posture_score, gesture_score, 
                                       eye_contact_score, movement_score) -> List[str]:
        """生成动作建议"""
        suggestions = []
        
        if posture_score < 80:
            suggestions.append("注意保持良好的站姿，肩膀放松，身体自然直立")
        if gesture_score < 80:
            suggestions.append("可以适当使用手势来辅助讲解，让表达更加生动")
        if eye_contact_score < 80:
            suggestions.append("尽量面向镜头/学生，保持眼神交流")
        if movement_score < 75:
            if movement_score < 70:
                suggestions.append("讲课时可以适当走动，避免过于僵硬")
            else:
                suggestions.append("注意控制走动幅度，避免过于频繁移动")
        
        if not suggestions:
            suggestions.append("动作表现良好，继续保持！")
        
        return suggestions

    
    # ==================== 语音识别 ====================
    
    async def _speech_to_text(self, video_path: str) -> Dict[str, Any]:
        """语音转文字"""
        if self.provider == "dashscope":
            return await self._dashscope_speech_to_text(video_path)
        elif self.provider == "whisper":
            return await self._whisper_speech_to_text(video_path)
        else:
            return await self._dashscope_speech_to_text(video_path)
    
    async def _dashscope_speech_to_text(self, video_path: str) -> Dict[str, Any]:
        """通过管理端配置的音频理解模型转写本地视频音轨。"""
        audio_path = await self._extract_audio(video_path)
        # A cloud transcription API cannot read a server-local file:// URL.
        return await self._simple_speech_recognition(audio_path)
    
    async def _simple_speech_recognition(self, audio_path: str) -> Dict[str, Any]:
        """使用配置的音频模型进行流式转写，并聚合为完整文本。"""
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        
        audio_base64 = base64.b64encode(audio_data).decode()
        config = await self._get_multimodal_config("audio")
        messages = [{
            "role": "user",
            "content": [
                {"type": "input_audio", "input_audio": {
                    "data": f"data:audio/wav;base64,{audio_base64}",
                    "format": "wav"
                }},
                {"type": "text", "text": "请将这段音频转录成文字，只输出转录的文字内容，不要添加任何解释或说明。"}
            ]
        }]
        
        try:
            result = await chat_completion(config, messages, stream=True)
            text = result["text"]
            
            # <sil> 表示静默/无语音
            if text in ("<sil>", ""):
                text = ""
            
            usage = result.get("usage", {})
            if usage:
                self._add_token_usage(
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0)
                )
                print(f"🔢 语音识别 Token: 输入={usage.get('prompt_tokens', 0)}, 输出={usage.get('completion_tokens', 0)}")
            
            return {"text": text.strip() if text else "(无语音内容)", "segments": []}
        except Exception as e:
            print(f"音频转录失败: {e}")
            return {"text": "(音频转录失败)", "segments": []}
    
    async def _whisper_speech_to_text(self, video_path: str) -> Dict[str, Any]:
        """使用 Whisper 进行语音识别"""
        audio_path = await self._extract_audio(video_path)
        
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language="zh")
            
            return {
                "text": result["text"],
                "segments": [
                    {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
                    for seg in result.get("segments", [])
                ]
            }
        except ImportError:
            raise RuntimeError("未安装 whisper 库")
    
    # ==================== 音视频处理 ====================
    
    async def _extract_audio(self, video_path: str) -> str:
        """从视频中提取音频"""
        audio_path = video_path.rsplit(".", 1)[0] + "_audio.wav"
        
        cmd = [
            ffmpeg_executable(), "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            "-y", audio_path
        ]
        
        process = await run_media_tool(cmd, timeout=300)
        
        if process.returncode != 0:
            raise RuntimeError(f"音频提取失败: {process.stderr.decode('utf-8', errors='replace')[-500:]}")
        
        return audio_path
    
    async def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        probe = shutil.which("ffprobe")
        if probe:
            process = await run_media_tool([
                probe, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path,
            ], timeout=30)
            if process.returncode == 0:
                try:
                    duration = float(process.stdout.decode().strip())
                    if duration > 0:
                        return duration
                except ValueError:
                    pass
        # The bundled FFmpeg wheel does not include ffprobe. Read metadata from
        # FFmpeg's input inspection, which exits without decoding the whole video.
        process = await run_media_tool([ffmpeg_executable(), "-hide_banner", "-i", video_path], timeout=30)
        metadata = process.stderr.decode("utf-8", errors="replace")
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", metadata)
        if match:
            duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
            if duration > 0:
                return duration
        raise RuntimeError("无法读取视频时长，请确认文件完整并使用 MP4 或 WebM 格式")
    
    # ==================== 文本分析 ====================
    
    def _analyze_text(self, text: str, segments: List[Dict], duration: float) -> Dict[str, Any]:
        """分析文字内容"""
        char_count = len(re.sub(r'[^\w]', '', text))
        speech_rate = (char_count / duration) * 60 if duration > 0 else 0
        pause_count = self._detect_pauses(segments, threshold=3.0)
        filler_words, filler_word_count = self._count_filler_words(text)
        time_distribution = self._analyze_time_distribution(text, segments)
        
        return {
            "char_count": char_count,
            "speech_rate": round(speech_rate, 1),
            "pause_count": pause_count,
            "filler_words": filler_words,
            "filler_word_count": filler_word_count,
            "time_distribution": time_distribution,
        }
    
    def _detect_pauses(self, segments: List[Dict], threshold: float = 3.0) -> int:
        """检测停顿次数"""
        if not segments or len(segments) < 2:
            return 0
        
        pause_count = 0
        for i in range(len(segments) - 1):
            gap = segments[i + 1]["start"] - segments[i]["end"]
            if gap >= threshold:
                pause_count += 1
        
        return pause_count
    
    def _count_filler_words(self, text: str) -> Tuple[Dict[str, int], int]:
        """统计语气词"""
        filler_patterns = [
            r'嗯+', r'啊+', r'呃+', r'额+',
            r'那个+', r'这个+', r'就是说',
            r'然后', r'对吧', r'是吧',
        ]
        
        filler_words = {}
        total_count = 0
        
        for pattern in filler_patterns:
            matches = re.findall(pattern, text)
            if matches:
                count = len(matches)
                filler_words[pattern.replace('+', '').replace('\\', '')] = count
                total_count += count
        
        return filler_words, total_count
    
    def _analyze_time_distribution(self, text: str, segments: List[Dict]) -> Dict[str, float]:
        """分析时间分配"""
        keywords = {
            "导入": ["同学们好", "今天我们", "上节课", "复习"],
            "新授": ["首先", "接下来", "我们来看", "重点"],
            "练习": ["练习", "做一做", "试一试", "完成"],
            "总结": ["总结", "回顾", "学到了", "下课"],
        }
        
        distribution = {}
        for phase, words in keywords.items():
            phase_time = 0
            for segment in segments:
                if any(word in segment["text"] for word in words):
                    phase_time += segment["end"] - segment["start"]
            distribution[phase] = round(phase_time, 1)
        
        return distribution
    
    # ==================== 综合评分 ====================
    
    def _calculate_overall_score(self, text_analysis: Dict, visual_analysis: Dict) -> float:
        """计算综合得分"""
        scores = []
        
        # 语速得分
        speech_rate = text_analysis["speech_rate"]
        if 120 <= speech_rate <= 160:
            speech_score = 100
        elif 100 <= speech_rate < 120 or 160 < speech_rate <= 180:
            speech_score = 80
        else:
            speech_score = 60
        scores.append(speech_score * 0.25)
        
        # 停顿得分
        pause_count = text_analysis["pause_count"]
        if pause_count <= 3:
            pause_score = 100
        elif pause_count <= 5:
            pause_score = 80
        else:
            pause_score = max(0, 100 - (pause_count - 5) * 10)
        scores.append(pause_score * 0.15)
        
        # 语气词得分
        filler_count = text_analysis["filler_word_count"]
        if filler_count <= 5:
            filler_score = 100
        elif filler_count <= 10:
            filler_score = 80
        else:
            filler_score = max(0, 100 - (filler_count - 10) * 5)
        scores.append(filler_score * 0.15)
        
        # 视觉分析得分
        if visual_analysis and "overall_gesture_score" in visual_analysis:
            scores.append(visual_analysis["overall_gesture_score"] * 0.45)
        elif visual_analysis and "posture_score" in visual_analysis:
            # 云端分析结果
            visual_score = (
                visual_analysis.get("posture_score", 80) * 0.2 +
                visual_analysis.get("gesture_score", 80) * 0.2 +
                visual_analysis.get("eye_contact_score", 80) * 0.2 +
                visual_analysis.get("expression_score", 80) * 0.2 +
                visual_analysis.get("movement_score", 80) * 0.2
            )
            scores.append(visual_score * 0.45)
        else:
            # 没有视觉分析，调整权重
            total_weight = 0.25 + 0.15 + 0.15
            scores = [s / total_weight for s in scores]
        
        return round(sum(scores), 1)
    
    def _generate_suggestions(self, text_analysis: Dict, visual_analysis: Dict) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        speech_rate = text_analysis["speech_rate"]
        if speech_rate < 100:
            suggestions.append("语速偏慢，建议适当加快，保持在120-160字/分钟")
        elif speech_rate > 180:
            suggestions.append("语速偏快，建议放慢节奏，让学生有时间思考")
        
        pause_count = text_analysis["pause_count"]
        if pause_count > 5:
            suggestions.append(f"检测到{pause_count}次较长停顿，建议提前熟悉教案，减少卡顿")
        
        filler_count = text_analysis["filler_word_count"]
        if filler_count > 10:
            suggestions.append(f"语气词使用较多（{filler_count}次），建议多练习，提高语言流畅度")
        
        if not suggestions:
            suggestions.append("语言表达流畅，继续保持！")
        
        return suggestions


# 全局实例
_video_analysis_service: Optional[VideoAnalysisService] = None


def get_video_analysis_service() -> VideoAnalysisService:
    """获取视频分析服务实例"""
    global _video_analysis_service
    if _video_analysis_service is None:
        _video_analysis_service = VideoAnalysisService()
    return _video_analysis_service
