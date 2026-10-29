"""
AI 服务核心模块
支持通义千问、OpenAI、DeepSeek 等多种大模型
"""
import json
import re
from typing import Optional, AsyncGenerator, Dict, Any, List
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore
import httpx

from app.core.config import settings
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
from app.services.document_parser import DocumentParser


class AIService:
    """AI 服务类，封装所有 AI 相关功能"""
    
    def __init__(self):
        """初始化 AI 客户端"""
        self.client: Optional[AsyncOpenAI] = None
        self.model: str = ""
        self._init_client()
    
    def _init_client(self):
        """根据配置初始化对应的 AI 客户端"""
        if not settings.AI_ENABLED:
            return
        
        provider = settings.AI_PROVIDER.lower()
        
        # 设置较长的超时时间（AI 生成可能需要 30-60 秒）
        timeout = httpx.Timeout(120.0, connect=30.0)
        
        if provider == "dashscope":
            if not settings.DASHSCOPE_API_KEY:
                raise ValueError("未配置 DASHSCOPE_API_KEY")
            self.client = AsyncOpenAI(
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.DASHSCOPE_BASE_URL,
                timeout=timeout,
            )
            self.model = settings.DASHSCOPE_MODEL
            
        elif provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("未配置 OPENAI_API_KEY")
            self.client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                timeout=timeout,
            )
            self.model = settings.OPENAI_MODEL
            
        elif provider == "deepseek":
            if not settings.DEEPSEEK_API_KEY:
                raise ValueError("未配置 DEEPSEEK_API_KEY")
            self.client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                timeout=timeout,
            )
            self.model = settings.DEEPSEEK_MODEL
        else:
            raise ValueError(f"不支持的 AI 服务商: {provider}")
    
    def _check_enabled(self):
        """检查 AI 功能是否启用"""
        if not settings.AI_ENABLED:
            raise RuntimeError("AI 功能未启用，请在配置中设置 AI_ENABLED=true")
        if not self.client:
            raise RuntimeError("AI 客户端未初始化，请检查 API Key 配置")
    
    async def _chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        调用 AI 完成对话
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            
        Returns:
            AI 回复内容
        """
        self._check_enabled()
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or settings.AI_TEMPERATURE,
            max_tokens=max_tokens or settings.AI_MAX_TOKENS,
        )
        
        return response.choices[0].message.content
    
    async def _chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式调用 AI
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            
        Yields:
            AI 回复内容片段
        """
        self._check_enabled()
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or settings.AI_TEMPERATURE,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 代码块
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取 { ... } 块
        brace_match = re.search(r'\{[\s\S]*\}', text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"无法从 AI 响应中提取 JSON: {text[:200]}...")
    
    # ==================== 教案分析功能 ====================
    
    async def analyze_lesson_plan(self, file_path: str) -> Dict[str, Any]:
        """
        分析教案质量
        
        Args:
            file_path: 教案文件路径
            
        Returns:
            分析结果字典
        """
        # 提取文本
        text = DocumentParser.extract_text(file_path)
        text = DocumentParser.truncate_text(text, 12000)
        
        # 构建 prompt
        prompt = LESSON_PLAN_ANALYSIS_PROMPT.format(lesson_plan_content=text)
        
        # 调用 AI
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # 分析任务使用较低温度
        )
        
        return self._extract_json(response)
    
    async def analyze_lesson_plan_from_text(self, text: str) -> Dict[str, Any]:
        """
        分析教案质量（直接传入文本）
        
        Args:
            text: 教案文本内容
            
        Returns:
            分析结果字典
        """
        text = DocumentParser.truncate_text(text, 12000)
        prompt = LESSON_PLAN_ANALYSIS_PROMPT.format(lesson_plan_content=text)
        
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        
        return self._extract_json(response)
    
    # ==================== 教案摘要功能 (老师端) ====================
    
    async def summarize_lesson_plan(self, file_path: str) -> Dict[str, Any]:
        """
        生成教案摘要（供老师快速浏览）
        
        Args:
            file_path: 教案文件路径
            
        Returns:
            摘要结果字典
        """
        text = DocumentParser.extract_text(file_path)
        text = DocumentParser.truncate_text(text, 10000)
        
        prompt = LESSON_PLAN_SUMMARY_PROMPT.format(lesson_plan_content=text)
        
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        
        return self._extract_json(response)
    
    async def summarize_lesson_plan_from_text(self, text: str) -> Dict[str, Any]:
        """生成教案摘要（直接传入文本）"""
        text = DocumentParser.truncate_text(text, 10000)
        prompt = LESSON_PLAN_SUMMARY_PROMPT.format(lesson_plan_content=text)
        
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        
        return self._extract_json(response)
    
    # ==================== 教案改进建议 ====================
    
    async def get_improvement_suggestions(self, file_path: str) -> Dict[str, Any]:
        """
        获取教案改进建议
        
        Args:
            file_path: 教案文件路径
            
        Returns:
            改进建议字典
        """
        text = DocumentParser.extract_text(file_path)
        text = DocumentParser.truncate_text(text, 12000)
        
        prompt = LESSON_PLAN_IMPROVEMENT_PROMPT.format(lesson_plan_content=text)
        
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        
        return self._extract_json(response)
    
    async def get_improvement_suggestions_from_text(self, text: str) -> Dict[str, Any]:
        """获取教案改进建议（直接传入文本）"""
        text = DocumentParser.truncate_text(text, 12000)
        prompt = LESSON_PLAN_IMPROVEMENT_PROMPT.format(lesson_plan_content=text)
        
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        
        return self._extract_json(response)
    
    # ==================== AI 评语生成 ====================
    
    async def generate_feedback(self, analysis_result: Dict[str, Any]) -> str:
        """
        根据分析结果生成评语
        
        Args:
            analysis_result: 教案分析结果
            
        Returns:
            评语文本
        """
        prompt = FEEDBACK_GENERATION_PROMPT.format(
            analysis_result=json.dumps(analysis_result, ensure_ascii=False, indent=2)
        )
        
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        
        return response.strip()
    
    # ==================== 教案生成 ====================
    
    def _build_template_section(
        self,
        template_type: str = "default",
        template_text: str = "",
    ) -> str:
        """
        构建模板部分的 Prompt
        
        Args:
            template_type: 模板类型 (default/interactive/inquiry/custom)
            template_text: 自定义模板内容（当 template_type 为 custom 时使用）
            
        Returns:
            模板 Prompt 片段
        """
        if template_type == "custom" and template_text:
            return CUSTOM_TEMPLATE_SECTION.format(template_content=template_text)
        elif template_type in BUILTIN_TEMPLATES:
            return BUILTIN_TEMPLATES[template_type]["content"]
        else:
            return DEFAULT_TEMPLATE_SECTION
    
    async def generate_lesson_plan(
        self,
        subject: str,
        grade: str,
        topic: str,
        duration: int = 15,
        key_point: str = "",
        difficulty: str = "",
        template_type: str = "default",
        template_text: str = "",
    ) -> str:
        """
        生成教案初稿
        
        Args:
            subject: 科目
            grade: 年级
            topic: 课题
            duration: 时长（分钟）
            key_point: 教学重点
            difficulty: 教学难点
            template_type: 模板类型 (default/interactive/inquiry/custom)
            template_text: 自定义模板内容
            
        Returns:
            教案内容（Markdown格式）
        """
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
        
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=6000,
        )
        
        return response
    
    async def generate_lesson_plan_stream(
        self,
        subject: str,
        grade: str,
        topic: str,
        duration: int = 15,
        key_point: str = "",
        difficulty: str = "",
        template_type: str = "default",
        template_text: str = "",
    ) -> AsyncGenerator[str, None]:
        """生成教案初稿（流式输出）"""
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
        
        async for chunk in self._chat_completion_stream(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        ):
            yield chunk
    
    # ==================== AI 备课助手 ====================
    
    def create_teaching_assistant_messages(
        self,
        lesson_plan_content: str,
        grade: str = "小学四年级",
        personality: str = "normal",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """
        创建备课助手的消息列表
        
        Args:
            lesson_plan_content: 教案内容
            grade: 年级
            personality: 性格类型 (curious/normal/challenging)
            conversation_history: 历史对话
            
        Returns:
            消息列表
        """
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
        lesson_plan_content: str,
        user_message: str,
        grade: str = "小学四年级",
        personality: str = "normal",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        与备课助手对话
        
        Args:
            lesson_plan_content: 教案内容
            user_message: 用户消息
            grade: 年级
            personality: 性格类型
            conversation_history: 历史对话
            
        Returns:
            AI 回复
        """
        messages = self.create_teaching_assistant_messages(
            lesson_plan_content=lesson_plan_content,
            grade=grade,
            personality=personality,
            conversation_history=conversation_history,
        )
        
        messages.append({"role": "user", "content": user_message})
        
        response = await self._chat_completion(
            messages=messages,
            temperature=0.8,
        )
        
        return response
    
    async def chat_with_teaching_assistant_stream(
        self,
        lesson_plan_content: str,
        user_message: str,
        grade: str = "小学四年级",
        personality: str = "normal",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """与备课助手对话（流式输出）"""
        messages = self.create_teaching_assistant_messages(
            lesson_plan_content=lesson_plan_content,
            grade=grade,
            personality=personality,
            conversation_history=conversation_history,
        )
        
        messages.append({"role": "user", "content": user_message})
        
        async for chunk in self._chat_completion_stream(
            messages=messages,
            temperature=0.8,
        ):
            yield chunk
    
    # ==================== 练习报告生成 ====================
    
    async def generate_practice_report(
        self,
        conversation_history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        生成备课练习报告
        
        Args:
            conversation_history: 对话历史
            
        Returns:
            报告字典
        """
        # 格式化对话历史
        formatted_history = "\n".join([
            f"{'老师' if msg['role'] == 'user' else 'AI学生'}: {msg['content']}"
            for msg in conversation_history
            if msg['role'] in ['user', 'assistant']
        ])
        
        prompt = PRACTICE_REPORT_PROMPT.format(conversation_history=formatted_history)
        
        response = await self._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        
        return self._extract_json(response)


# 全局 AI 服务实例（延迟初始化）
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """获取 AI 服务实例"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
