"""Regression checks using real HTTP serialization and mocked provider responses.

Run: python -m unittest discover -s backend/tests -v
These checks do not need database drivers, provider credentials, or network access.
"""
import base64
from functools import partial
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import wave

import httpx


SERVICES = Path(__file__).resolve().parents[1] / "app" / "services"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Import the HTTP service independently of the application's database startup.
model_api = load_module("model_api_under_test", SERVICES / "model_api.py")


def config(model_type="text", model_id="qwen-flash"):
    return {
        "provider": "dashscope", "api_key": "sk-test-secret",
        "api_base_url": "https://regional.example/compatible-mode/v1/",
        "model_id": model_id, "model_type": model_type,
    }


class SplitStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        events = [
            {"choices": [{"delta": {"content": "同学们"}}]},
            {"choices": [{"delta": {"content": "好"}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 4}},
        ]
        body = "".join("data: " + json.dumps(event, ensure_ascii=False) + "\n\n" for event in events)
        raw = (body + "data: [DONE]\n\n").encode("utf-8")
        # Deliberately split events and multibyte Chinese characters.
        for index in range(0, len(raw), 7):
            yield raw[index:index + 7]


class ModelAPITests(unittest.IsolatedAsyncioTestCase):
    def mock_http(self, handler):
        original = httpx.AsyncClient
        return patch.object(model_api.httpx, "AsyncClient", partial(original, transport=httpx.MockTransport(handler)))

    def json_response(self, text="OK"):
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 3}})

    async def test_text_uses_configured_endpoint_and_key(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://regional.example/compatible-mode/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"], "Bearer sk-test-secret")
            payload = json.loads(request.content)
            self.assertIsInstance(payload["messages"][0]["content"], str)
            self.assertEqual(payload["model"], "qwen-flash")
            return self.json_response()
        with self.mock_http(handler):
            self.assertEqual((await model_api.check_model_connection(config()))["text"], "OK")

    async def test_vision_sends_a_local_valid_image(self):
        def handler(request):
            payload = json.loads(request.content)
            image = payload["messages"][0]["content"][0]
            self.assertEqual(image["type"], "image_url")
            data = base64.b64decode(image["image_url"]["url"].split(",", 1)[1])
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(int.from_bytes(data[16:20], "big"), 32)
            return self.json_response("白色")
        with self.mock_http(handler):
            result = await model_api.check_model_connection(config("vision", "qwen-vl-max"))
        self.assertEqual(result["text"], "白色")

    async def test_audio_streams_and_assembles_text_and_usage(self):
        def handler(request):
            payload = json.loads(request.content)
            self.assertTrue(payload["stream"])
            self.assertEqual(payload["modalities"], ["text"])
            self.assertEqual(payload["model"], "qwen-omni-turbo")
            audio = payload["messages"][0]["content"][0]["input_audio"]
            with wave.open(io.BytesIO(base64.b64decode(audio["data"].split(",", 1)[1]))) as sample:
                self.assertEqual(sample.getframerate(), 16000)
                self.assertEqual(sample.getnchannels(), 1)
                self.assertEqual(sample.getnframes(), 16000)
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=SplitStream())
        with self.mock_http(handler):
            result = await model_api.check_model_connection(config("audio", "qwen-omni-turbo"))
        self.assertEqual(result, {"text": "同学们好", "usage": {"prompt_tokens": 12, "completion_tokens": 4}})

    async def test_provider_error_is_reported_without_exposing_key(self):
        def handler(request):
            return httpx.Response(401, json={"error": {"code": "invalid_api_key", "message": "Invalid sk-test-secret"}})
        with self.mock_http(handler), self.assertRaises(model_api.ModelAPIError) as caught:
            await model_api.check_model_connection(config())
        self.assertIn("HTTP 401 / invalid_api_key", str(caught.exception))
        self.assertNotIn("sk-test-secret", str(caught.exception))

    async def test_stream_error_is_not_reported_as_success(self):
        event = 'data: {"error":{"code":"quota_exceeded","message":"No quota"}}\n\n'
        with self.mock_http(lambda request: httpx.Response(200, headers={"content-type": "text/event-stream"}, content=event)):
            with self.assertRaisesRegex(model_api.ModelAPIError, "quota_exceeded"):
                await model_api.check_model_connection(config("audio", "qwen-omni-turbo"))

    async def test_truncated_stream_is_rejected(self):
        event = 'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        with self.mock_http(lambda request: httpx.Response(200, headers={"content-type": "text/event-stream"}, content=event)):
            with self.assertRaisesRegex(model_api.ModelAPIError, "不完整"):
                await model_api.check_model_connection(config("audio", "qwen-omni-turbo"))

    async def test_html_endpoint_is_rejected(self):
        with self.mock_http(lambda request: httpx.Response(200, text="<html>wrong endpoint</html>")):
            with self.assertRaisesRegex(model_api.ModelAPIError, "Base URL"):
                await model_api.check_model_connection(config())

    async def test_network_failure_has_an_actionable_message(self):
        def handler(request):
            raise httpx.ConnectError("connection refused", request=request)
        with self.mock_http(handler), self.assertRaisesRegex(model_api.ModelAPIError, "网络或代理"):
            await model_api.check_model_connection(config())

    def test_default_region_and_already_complete_url(self):
        default = config()
        default["api_base_url"] = ""
        self.assertEqual(model_api.resolve_chat_url(default), "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        default["api_base_url"] = "https://regional.example/v1/chat/completions/"
        self.assertEqual(model_api.resolve_chat_url(default), "https://regional.example/v1/chat/completions")

    async def test_invalid_configuration_fails_before_network(self):
        bad = config()
        bad["api_key"] = "中文密钥"
        with self.assertRaisesRegex(model_api.ModelAPIError, "API Key"):
            await model_api.check_model_connection(bad)
        bad = config()
        bad["api_base_url"] = "not-a-url"
        with self.assertRaisesRegex(model_api.ModelAPIError, "Base URL"):
            await model_api.check_model_connection(bad)

    def load_video_service(self):
        configuration = ModuleType("app.core.config")
        configuration.settings = SimpleNamespace(AI_PROVIDER="dashscope")
        with patch.dict(sys.modules, {"app.core.config": configuration, "app.services.model_api": model_api}):
            video = load_module("video_service_under_test", SERVICES / "video_analysis_service.py")
        return video.VideoAnalysisService()

    async def test_actual_audio_uses_admin_model_endpoint_and_stream(self):
        service = self.load_video_service()
        service._get_db_config = AsyncMock(return_value=config("audio", "configured-omni-model"))
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "configured-omni-model")
            self.assertTrue(payload["stream"])
            self.assertEqual(request.url.host, "regional.example")
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=SplitStream())
        with tempfile.TemporaryDirectory() as temporary:
            audio = Path(temporary) / "sample.wav"
            audio.write_bytes(b"test-audio")
            with self.mock_http(handler):
                result = await service._simple_speech_recognition(str(audio))
        self.assertEqual(result["text"], "同学们好")
        self.assertEqual(service.token_usage["total_tokens"], 16)

    async def test_video_audio_uses_configured_transcriber_directly(self):
        service = self.load_video_service()
        service._extract_audio = AsyncMock(return_value="local.wav")
        service._simple_speech_recognition = AsyncMock(return_value={"text": "课堂内容", "segments": []})
        result = await service._dashscope_speech_to_text("local.mp4")
        service._simple_speech_recognition.assert_awaited_once_with("local.wav")
        self.assertEqual(result["text"], "课堂内容")

    async def test_actual_vision_uses_admin_endpoint_and_parses_scores(self):
        service = self.load_video_service()
        service._get_db_config = AsyncMock(return_value=config("vision", "configured-vl-model"))
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(request.url.host, "regional.example")
            self.assertEqual(payload["model"], "configured-vl-model")
            self.assertEqual(payload["messages"][0]["content"][0]["image_url"]["url"], "data:image/jpeg;base64,test")
            return self.json_response('{"posture_score":85,"overall_gesture_score":81}')
        with self.mock_http(handler):
            result = await service._call_vision_model(["data:image/jpeg;base64,test"])
        self.assertEqual(result["posture_score"], 85)
        self.assertEqual(service.token_usage["input_tokens"], 3)


if __name__ == "__main__":
    unittest.main()
