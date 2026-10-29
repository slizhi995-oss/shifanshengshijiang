"""
AI 模型配置服务
支持从数据库动态获取模型配置，实现模型切换功能
"""
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, AsyncGenerator
from urllib.parse import urlsplit
from openai import AsyncOpenAI
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIModelConfig, AIModelUsageLog
from app.core.config import settings
from app.core.database import async_session_factory
from app.services.ai_prompts import (
    LESSON_PLAN_ANALYSIS_PROMPT,
    LESSON_PLAN_SUMMARY_PROMPT,
    LESSON_PLAN_IMPROVEMENT_PROMPT,
    FEEDBACK_GENERATION_PROMPT,
    LESSON_PLAN_GENERATION_PROMPT,
    TEACHING_ASSISTANT_SYSTEM_PROMPT,
    CLASSROOM_SIMULATION_PROMPT,
    PRACTICE_REPORT_PROMPT,
    PERSONALITY_TYPES,
    DEFAULT_TEMPLATE_SECTION,
    CUSTOM_TEMPLATE_SECTION,
    BUILTIN_TEMPLATES,
)
import re
from app.services.document_parser import DocumentParser
from app.services.lesson_content import PRESENTATION_RULES


class StructuredOutputTruncatedError(ValueError):
    """The provider exhausted its output budget before completing JSON."""


def _supports_dashscope_json_output(config: AIModelConfig) -> bool:
    """Enable documented text/vision JSON modes only on native endpoints."""
    if config.provider.strip().lower() != "dashscope":
        return False
    supported = (config.model_type == 'text' and re.fullmatch(r'qwen-flash(?:-\d{4}-\d{2}-\d{2})?',config.model_id)) or (
        config.model_type == 'vision' and re.fullmatch(r'qwen3-vl-(?:plus|flash)(?:-\d{4}-\d{2}-\d{2})?',config.model_id))
    if not supported:
        return False
    base = config.api_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    try:
        parts = urlsplit(base.strip().rstrip("/"))
        hostname = parts.hostname or ""
        native_host = hostname in {
            "dashscope.aliyuncs.com",
            "dashscope-intl.aliyuncs.com",
            "dashscope-us.aliyuncs.com",
        } or re.fullmatch(r"[a-z0-9-]+\.(?:cn-beijing|ap-southeast-1)\.maas\.aliyuncs\.com", hostname)
        return bool(
            native_host
            and parts.scheme == "https"
            and parts.port in (None, 443)
            and parts.path == "/compatible-mode/v1"
            and not parts.username
            and not parts.password
            and not parts.query
            and not parts.fragment
        )
    except ValueError:
        return False


class DynamicAIService:
    """
    动态 AI 服务类
    支持根据数据库配置动态切换模型
    """
    
    def __init__(self):
        self._clients: Dict[int, AsyncOpenAI] = {}  # 模型ID -> 客户端缓存
        self._default_configs: Dict[str, AIModelConfig] = {}  # 模型类型 -> 默认配置
    
    async def _get_model_config(
        self, 
        db: AsyncSession,
        model_id: Optional[int] = None,
        model_type: str = "text"
    ) -> Optional[AIModelConfig]:
        """
        获取模型配置
        
        Args:
            db: 数据库会话
            model_id: 指定模型ID，如果不指定则返回默认模型
            model_type: 模型类型 (text/audio/vision)
            
        Returns:
            模型配置对象
        """
        if model_id:
            # 获取指定的模型
            result = await db.execute(
                select(AIModelConfig).where(
                    AIModelConfig.id == model_id,
                    AIModelConfig.is_enabled == True
                )
            )
            return result.scalar_one_or_none()
        else:
            # 获取该类型的默认模型
            result = await db.execute(
                select(AIModelConfig).where(
                    AIModelConfig.model_type == model_type,
                    AIModelConfig.is_enabled == True,
                    AIModelConfig.is_default == True
                )
            )
            config = result.scalar_one_or_none()
            
            if not config:
                # 如果没有默认模型，取优先级最高的启用模型
                result = await db.execute(
                    select(AIModelConfig)
                    .where(
                        AIModelConfig.model_type == model_type,
                        AIModelConfig.is_enabled == True
                    )
                    .order_by(AIModelConfig.priority.asc())
                    .limit(1)
                )
                config = result.scalar_one_or_none()
            
            return config
    
    async def _get_client(
        self, 
        config: AIModelConfig
    ) -> AsyncOpenAI:
        """
        获取或创建 AI 客户端
        
        Args:
            config: 模型配置
            
        Returns:
            AsyncOpenAI 客户端
        """
        # 构建 base_url
        timeout = httpx.Timeout(120.0, connect=30.0)
        
        provider = config.provider.lower()
        base_url = config.api_base_url
        
        if not base_url:
            # 使用默认的 base_url
            if provider == "dashscope":
                base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            elif provider == "openai":
                base_url = "https://api.openai.com/v1"
            elif provider == "deepseek":
                base_url = "https://api.deepseek.com/v1"
            elif provider == "zhipu":
                base_url = "https://open.bigmodel.cn/api/paas/v4/"
            elif provider == "moonshot":
                base_url = "https://api.moonshot.cn/v1"
            elif provider == "anthropic":
                base_url = "https://api.anthropic.com/v1"
            else:
                base_url = "https://api.openai.com/v1"  # 默认 OpenAI 兼容
        
        # 验证 API Key 不包含非 ASCII 字符（如中文），避免 UnicodeEncodeError
        api_key = config.api_key.strip() if config.api_key else ""
        try:
            api_key.encode('ascii')
        except UnicodeEncodeError:
            raise RuntimeError(
                f"模型 [{config.name}] 的 API Key 包含非法字符（如中文），请在 AI 模型配置中修正"
            )
        
        if not api_key:
            raise RuntimeError(f"模型 [{config.name}] 的 API Key 为空，请在 AI 模型配置中设置")

        # 管理员更新凭据或接口后，下一次业务调用必须使用最新配置。
        # 不关闭旧客户端，避免中断仍在使用它的并发请求。
        cached = self._clients.get(config.id)
        if (
            cached is not None
            and cached.api_key == api_key
            and str(cached.base_url).rstrip("/") == base_url.rstrip("/")
        ):
            return cached
        
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        
        self._clients[config.id] = client
        return client
    
    async def chat_completion(
        self,
        db: AsyncSession,
        messages: List[Dict[str, str]],
        user_id: Optional[int] = None,
        model_id: Optional[int] = None,
        model_type: str = "text",
        usage_type: str = "chat",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        structured_output: bool = False,
    ) -> str:
        """
        调用 AI 完成对话
        
        Args:
            db: 数据库会话
            messages: 消息列表
            user_id: 用户ID（用于记录日志）
            model_id: 指定模型ID
            model_type: 模型类型
            usage_type: 使用类型（用于日志）
            temperature: 温度参数
            max_tokens: 最大 token 数
            structured_output: 请求 JSON 输出；仅受支持的原生百炼模型启用 JSON mode
            
        Returns:
            AI 回复内容
        """
        start_time = datetime.now()
        
        # 获取模型配置
        config = await self._get_model_config(db, model_id, model_type)
        if not config:
            raise RuntimeError(f"未找到可用的 {model_type} 模型，请先在管理后台配置")
        
        # 获取客户端
        client = await self._get_client(config)
        
        # 使用配置的参数
        temp = temperature if temperature is not None else config.temperature
        tokens = max_tokens if max_tokens is not None else config.max_tokens
        
        error_message = None
        response_content = ""
        prompt_tokens = 0
        completion_tokens = 0
        
        try:
            parameters = {
                "model": config.model_id,
                "messages": messages,
                "temperature": temp,
                "max_tokens": tokens,
            }
            if structured_output and _supports_dashscope_json_output(config):
                # Qwen-Flash and Qwen3-VL support JSON Object output.
                # https://help.aliyun.com/zh/model-studio/qwen-structured-output
                parameters["response_format"] = {"type": "json_object"}
                if config.model_type == 'text':
                    parameters["extra_body"] = {"enable_thinking": False}
            response = await client.chat.completions.create(**parameters)
            
            response_content = response.choices[0].message.content
            
            # 获取 token 使用量
            if hasattr(response, 'usage') and response.usage:
                prompt_tokens = response.usage.prompt_tokens or 0
                completion_tokens = response.usage.completion_tokens or 0

            if structured_output and getattr(response.choices[0], "finish_reason", None) == "length":
                raise StructuredOutputTruncatedError(
                    "模型输出达到长度上限，JSON 数据已截断，请减少单次生成内容或提高模型输出长度"
                )
            
        except asyncio.CancelledError:
            error_message = "模型请求已取消或等待超时"
            raise
        except Exception as e:
            error_message = str(e)
            raise
        
        finally:
            # 记录使用日志
            end_time = datetime.now()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            total_tokens = prompt_tokens + completion_tokens
            estimated_cost = total_tokens / 1000 * config.price_per_1k_tokens
            
            usage_log = AIModelUsageLog(
                model_config_id=config.id,
                user_id=user_id,
                usage_type=usage_type,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                latency_ms=latency_ms,
                estimated_cost=estimated_cost,
                is_success=error_message is None,
                error_message=error_message,
            )
            db.add(usage_log)
            await db.commit()
        
        return response_content
    
    async def chat_completion_stream(
        self,
        db: AsyncSession,
        messages: List[Dict[str, str]],
        user_id: Optional[int] = None,
        model_id: Optional[int] = None,
        model_type: str = "text",
        usage_type: str = "chat",
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式调用 AI
        
        Args:
            db: 数据库会话
            messages: 消息列表
            user_id: 用户ID
            model_id: 指定模型ID
            model_type: 模型类型
            usage_type: 使用类型
            temperature: 温度参数
            
        Yields:
            AI 回复内容片段
        """
        start_time = datetime.now()
        
        # 获取模型配置
        config = await self._get_model_config(db, model_id, model_type)
        if not config:
            raise RuntimeError(f"未找到可用的 {model_type} 模型，请先在管理后台配置")
        
        # 获取客户端
        client = await self._get_client(config)
        
        temp = temperature if temperature is not None else config.temperature
        
        error_message = None
        total_content = ""
        
        try:
            stream = await client.chat.completions.create(
                model=config.model_id,
                messages=messages,
                temperature=temp,
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_content += content
                    yield content
        
        except Exception as e:
            error_message = str(e)
            raise
        
        finally:
            # 记录使用日志（流式模式估算 token）
            end_time = datetime.now()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # 简单估算 token 数（约 4 字符/token）
            estimated_prompt_tokens = sum(
                len(m.get("content", "")) // 4 for m in messages
            )
            estimated_completion_tokens = len(total_content) // 4
            total_tokens = estimated_prompt_tokens + estimated_completion_tokens
            estimated_cost = total_tokens / 1000 * config.price_per_1k_tokens
            
            usage_log = AIModelUsageLog(
                model_config_id=config.id,
                user_id=user_id,
                usage_type=usage_type,
                input_tokens=estimated_prompt_tokens,
                output_tokens=estimated_completion_tokens,
                latency_ms=latency_ms,
                estimated_cost=estimated_cost,
                is_success=error_message is None,
                error_message=error_message,
            )
            db.add(usage_log)
            await db.commit()
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        brace_match = re.search(r'\{[\s\S]*\}', text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # 尝试修复常见的 JSON 错误
        try:
            return json.loads(text.replace("'", '"'))
        except:
            pass
            
        raise ValueError(f"无法从 AI 响应中提取 JSON: {text[:200]}...")

    async def analyze_lesson_plan_from_text(
        self, 
        db: AsyncSession,
        text: str,
        user_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """分析教案质量"""
        text = DocumentParser.truncate_text(text, 12000)
        prompt = LESSON_PLAN_ANALYSIS_PROMPT.format(lesson_plan_content=text)
        
        response = await self.chat_completion(
            db=db,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            model_id=model_id,
            usage_type="analysis",
            temperature=0.3,
        )
        return self._extract_json(response)

    async def summarize_lesson_plan_from_text(
        self, 
        db: AsyncSession,
        text: str,
        user_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """生成教案摘要"""
        text = DocumentParser.truncate_text(text, 10000)
        prompt = LESSON_PLAN_SUMMARY_PROMPT.format(lesson_plan_content=text)
        
        response = await self.chat_completion(
            db=db,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            model_id=model_id,
            usage_type="summary",
            temperature=0.3,
        )
        return self._extract_json(response)

    async def get_improvement_suggestions_from_text(
        self, 
        db: AsyncSession,
        text: str,
        user_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取教案改进建议"""
        text = DocumentParser.truncate_text(text, 12000)
        prompt = LESSON_PLAN_IMPROVEMENT_PROMPT.format(lesson_plan_content=text)
        
        response = await self.chat_completion(
            db=db,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            model_id=model_id,
            usage_type="improvement",
            temperature=0.5,
        )
        return self._extract_json(response)

    async def generate_feedback(
        self,
        db: AsyncSession,
        analysis_result: Dict[str, Any],
        user_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> str:
        """生成 AI 评语"""
        prompt = FEEDBACK_GENERATION_PROMPT.format(
            analysis_result=json.dumps(analysis_result, ensure_ascii=False, indent=2)
        )
        
        response = await self.chat_completion(
            db=db,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            model_id=model_id,
            usage_type="feedback",
            temperature=0.7,
        )
        return response.strip()

    def _build_template_section(self, template_type: str, template_text: str) -> str:
        if template_type == "custom" and template_text:
            return CUSTOM_TEMPLATE_SECTION.format(template_content=template_text)
        elif template_type in BUILTIN_TEMPLATES:
            return BUILTIN_TEMPLATES[template_type]["content"]
        else:
            return DEFAULT_TEMPLATE_SECTION

    async def generate_lesson_plan(
        self,
        db: AsyncSession,
        subject: str,
        grade: str,
        topic: str,
        duration: int,
        key_point: str,
        difficulty: str,
        template_type: str,
        template_text: str,
        user_id: Optional[int] = None,
        model_id: Optional[int] = None,
        textbook_context: Optional[dict] = None,
    ) -> str:
        """生成教案初稿"""
        template_section = self._build_template_section(template_type, template_text)
        
        prompt = LESSON_PLAN_GENERATION_PROMPT.format(
            subject=subject,
            grade=grade,
            topic=topic,
            duration=duration,
            key_point=key_point or "由 AI 自动设定",
            difficulty=difficulty or "由 AI 自动设定",
            template_section=template_section,
        )
        
        messages = [{"role": "user", "content": prompt + PRESENTATION_RULES}]
        if textbook_context:
            from app.services.textbook_service import retrieval_prompt
            messages.insert(0, {"role": "system", "content": retrieval_prompt(textbook_context)})
        return await self.chat_completion(
            db=db,
            messages=messages,
            user_id=user_id,
            model_id=model_id,
            usage_type="generation",
            temperature=0.7,
            max_tokens=6000,
        )

    async def generate_lesson_plan_stream(
        self,
        db: AsyncSession,
        subject: str,
        grade: str,
        topic: str,
        duration: int,
        key_point: str,
        difficulty: str,
        template_type: str,
        template_text: str,
        user_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """生成教案初稿（流式）"""
        template_section = self._build_template_section(template_type, template_text)
        
        prompt = LESSON_PLAN_GENERATION_PROMPT.format(
            subject=subject,
            grade=grade,
            topic=topic,
            duration=duration,
            key_point=key_point or "由 AI 自动设定",
            difficulty=difficulty or "由 AI 自动设定",
            template_section=template_section,
        )
        
        async for chunk in self.chat_completion_stream(
            db=db,
            messages=[{"role": "user", "content": prompt + PRESENTATION_RULES}],
            user_id=user_id,
            model_id=model_id,
            usage_type="generation_stream",
            temperature=0.7,
        ):
            yield chunk

    def create_teaching_assistant_messages(
        self,
        lesson_plan_content: str,
        grade: str,
        personality: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        max_chars = settings.AI_LESSON_PLAN_MAX_CHARS
        if personality == "classroom_simulation":
            # 课堂模拟模式 - 使用专用的多角色模拟 prompt
            system_prompt = CLASSROOM_SIMULATION_PROMPT.format(
                grade=grade,
                lesson_plan_content=DocumentParser.truncate_text(lesson_plan_content, max_chars),
            )
        else:
            personality_desc = PERSONALITY_TYPES.get(personality, PERSONALITY_TYPES["normal"])
            system_prompt = TEACHING_ASSISTANT_SYSTEM_PROMPT.format(
                grade=grade,
                personality=personality_desc,
                lesson_plan_content=DocumentParser.truncate_text(lesson_plan_content, max_chars),
            )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            messages.extend(conversation_history)
        
        return messages

    async def chat_with_teaching_assistant(
        self,
        db: AsyncSession,
        lesson_plan_content: str,
        user_message: str,
        grade: str,
        personality: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> str:
        """与备课助手对话"""
        messages = self.create_teaching_assistant_messages(
            lesson_plan_content=lesson_plan_content,
            grade=grade,
            personality=personality,
            conversation_history=conversation_history,
        )
        
        messages.append({"role": "user", "content": user_message})
        
        return await self.chat_completion(
            db=db,
            messages=messages,
            user_id=user_id,
            model_id=model_id,
            usage_type="assistant_chat",
            temperature=0.8,
        )

    async def chat_with_teaching_assistant_stream(
        self,
        db: AsyncSession,
        lesson_plan_content: str,
        user_message: str,
        grade: str,
        personality: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """与备课助手对话（流式）"""
        messages = self.create_teaching_assistant_messages(
            lesson_plan_content=lesson_plan_content,
            grade=grade,
            personality=personality,
            conversation_history=conversation_history,
        )
        
        messages.append({"role": "user", "content": user_message})
        
        async for chunk in self.chat_completion_stream(
            db=db,
            messages=messages,
            user_id=user_id,
            model_id=model_id,
            usage_type="assistant_chat_stream",
            temperature=0.8,
        ):
            yield chunk

    async def generate_practice_report(
        self,
        db: AsyncSession,
        conversation_history: List[Dict[str, str]],
        user_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """生成备课练习报告"""
        formatted_history = "\n".join([
            f"{'老师' if msg['role'] == 'user' else 'AI学生'}: {msg['content']}"
            for msg in conversation_history
            if msg['role'] in ['user', 'assistant']
        ])
        
        prompt = PRACTICE_REPORT_PROMPT.format(conversation_history=formatted_history)
        
        response = await self.chat_completion(
            db=db,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            model_id=model_id,
            usage_type="report",
            temperature=0.3,
        )
        return self._extract_json(response)


# 全局实例
_dynamic_ai_service: Optional[DynamicAIService] = None


def get_dynamic_ai_service() -> DynamicAIService:
    """获取动态 AI 服务实例"""
    global _dynamic_ai_service
    if _dynamic_ai_service is None:
        _dynamic_ai_service = DynamicAIService()
    return _dynamic_ai_service
