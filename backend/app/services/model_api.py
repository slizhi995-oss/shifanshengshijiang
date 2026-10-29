"""OpenAI-compatible requests shared by model tests and multimodal analysis."""
import base64
import io
import json
import struct
import wave
import zlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import httpx


DEFAULT_BASE_URLS = {
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
}


class ModelAPIError(RuntimeError):
    """A provider error that can safely be shown to the model administrator."""


def resolve_chat_url(config: Dict[str, Any]) -> str:
    base = (config.get("api_base_url") or "").strip().rstrip("/")
    if not base:
        base = DEFAULT_BASE_URLS.get(str(config.get("provider", "")).lower(), "")
    parts = urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.query or parts.fragment:
        raise ModelAPIError("请填写有效的 OpenAI 兼容 API Base URL")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


async def check_model_connection(config: Dict[str, Any]) -> Dict[str, Any]:
    """Probe the selected modality with local fixtures, without external file URLs."""
    model_type = config.get("model_type", "text")
    if model_type == "audio":
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\x00\x00" * 16000)
        sample = base64.b64encode(buffer.getvalue()).decode("ascii")
        content = [
            {"type": "input_audio", "input_audio": {"data": f"data:audio/wav;base64,{sample}", "format": "wav"}},
            {"type": "text", "text": "这是一段静音测试音频，如果没有人声，请只回复无语音。"},
        ]
    elif model_type == "vision":
        def chunk(kind: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        # A valid 32 x 32 white PNG; no network fetch is needed by the provider.
        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", struct.pack(">IIBBBBB", 32, 32, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress((b"\x00" + b"\xff" * 96) * 32))
        png += chunk(b"IEND", b"")
        sample = base64.b64encode(png).decode("ascii")
        content = [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{sample}"}},
            {"type": "text", "text": "图片是什么颜色？只回复颜色。"},
        ]
    elif model_type == "text":
        content = "Reply OK."
    else:
        raise ModelAPIError("不支持的模型类型，请选择文本、音频或视觉模型")
    use_stream = model_type == "audio" or "omni" in config["model_id"].lower()
    return await chat_completion(
        config, [{"role": "user", "content": content}],
        stream=use_stream, max_tokens=None if use_stream else 16,
    )


def _provider_error(data: Dict[str, Any], api_key: str, status: int = 200) -> ModelAPIError:
    error = data.get("error") or data
    if not isinstance(error, dict):
        error = {"message": str(error)}
    code = str(error.get("code") or error.get("type") or "request_failed")
    message = str(error.get("message") or "模型服务拒绝了请求")
    # Provider responses can echo credentials; never return the configured key.
    safe_detail = f"HTTP {status} / {code}: {message}".replace(api_key, "***")
    return ModelAPIError(safe_detail[:600])


async def chat_completion(
    config: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    stream: bool = False,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Return assembled text and usage, including for streaming-only Omni models."""
    api_key = (config.get("api_key") or "").strip()
    if not api_key or not api_key.isascii():
        raise ModelAPIError("API Key 为空或包含非法字符，请重新填写")
    url = resolve_chat_url(config)
    payload = {"model": config["model_id"], "messages": messages, "stream": stream}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if stream:
        payload["stream_options"] = {"include_usage": True}
    if config.get("model_type") == "audio" or "omni" in config["model_id"].lower():
        payload["modalities"] = ["text"]
    headers = {"Authorization": f"Bearer {api_key}"}
    text_parts = []
    usage = {}
    saw_response = False
    finished = False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                is_sse = "text/event-stream" in response.headers.get("content-type", "")
                if response.is_error or not is_sse:
                    body = await response.aread()
                    try:
                        data = json.loads(body)
                    except (ValueError, UnicodeDecodeError):
                        raise ModelAPIError(f"HTTP {response.status_code}: 模型接口未返回有效 JSON，请检查 Base URL")
                    if response.is_error or data.get("error"):
                        raise _provider_error(data, api_key, response.status_code)
                    choices = data.get("choices") or []
                    if not choices:
                        raise ModelAPIError("模型接口未返回对话结果，请检查模型与接口是否匹配")
                    return {"text": choices[0].get("message", {}).get("content") or "", "usage": data.get("usage") or {}}

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    event = line[5:].strip()
                    if event == "[DONE]":
                        finished = True
                        break
                    if not event:
                        continue
                    data = json.loads(event)
                    if data.get("error"):
                        raise _provider_error(data, api_key)
                    if data.get("usage"):
                        usage = data["usage"]
                    for choice in data.get("choices") or []:
                        saw_response = True
                        if choice.get("finish_reason"):
                            finished = True
                        content = choice.get("delta", {}).get("content")
                        if content:
                            text_parts.append(content)
                if not saw_response or not finished:
                    raise ModelAPIError("模型流式响应不完整，请重试")
                return {"text": "".join(text_parts), "usage": usage}
    except httpx.TimeoutException as exc:
        raise ModelAPIError("模型服务连接或响应超时，请稍后重试") from exc
    except httpx.RequestError as exc:
        raise ModelAPIError("无法连接模型服务，请检查 Base URL、网络或代理") from exc
    except (ValueError, TypeError, AttributeError) as exc:
        raise ModelAPIError("模型响应格式不正确，请检查模型与接口是否匹配") from exc
