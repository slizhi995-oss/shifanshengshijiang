"""Run from backend: .venv/Scripts/python -m unittest discover -s tests -p test_ai_config_refresh.py -v"""
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from openai import AsyncOpenAI

from app.api.routes import ai as routes
from app.services import ai_model_service as models


def configuration():
    return SimpleNamespace(
        id=1, name="Test text model", model_type="text", model_id="test-text",
        provider="dashscope", api_key="old-test-key",
        api_base_url="https://old.example/v1", temperature=0.7,
        max_tokens=256, price_per_1k_tokens=0.0,
    )


class AIConfigRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = models.DynamicAIService()
        self.config = configuration()
        self.clients = []
        self.requests = []

        def handler(request):
            self.requests.append(request)
            return httpx.Response(200, json={
                "id": "test", "object": "chat.completion", "created": 0,
                "model": "test-text",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            })

        def make_client(**kwargs):
            client = AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
            self.clients.append(client)
            return client

        self.factory_patch = patch.object(models, "AsyncOpenAI", side_effect=make_client)
        self.factory_patch.start()

    async def asyncTearDown(self):
        self.factory_patch.stop()
        for client in self.clients:
            await client.close()

    async def test_unchanged_config_reuses_client(self):
        first = await self.service._get_client(self.config)
        self.assertIs(first, await self.service._get_client(self.config))

    async def test_changed_key_is_sent_on_next_call(self):
        first = await self.service._get_client(self.config)
        self.config.api_key = "new-test-key"
        second = await self.service._get_client(self.config)
        self.assertIsNot(first, second)
        await second.chat.completions.create(model="test-text", messages=[{"role": "user", "content": "Hi"}])
        self.assertEqual(self.requests[-1].headers["Authorization"], "Bearer new-test-key")
        self.assertFalse(first.is_closed())

    async def test_changed_endpoint_is_used_on_next_call(self):
        first = await self.service._get_client(self.config)
        self.config.api_base_url = "https://new.example/v1/"
        second = await self.service._get_client(self.config)
        self.assertIsNot(first, second)
        await second.chat.completions.create(model="test-text", messages=[{"role": "user", "content": "Hi"}])
        self.assertEqual(str(self.requests[-1].url), "https://new.example/v1/chat/completions")

    async def test_invalid_new_key_does_not_reuse_old_client(self):
        await self.service._get_client(self.config)
        self.config.api_key = ""
        with self.assertRaises(RuntimeError):
            await self.service._get_client(self.config)

    async def test_assistant_uses_updated_key_without_restart(self):
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: self.config)),
            add=Mock(), commit=AsyncMock(),
        )
        request = routes.TeachingAssistantStartRequest(lesson_plan_text="Lesson content")
        with patch.object(routes, "get_dynamic_ai_service", return_value=self.service), patch.object(routes.settings, "AI_ENABLED", True):
            for key in ("old-test-key", "new-test-key"):
                self.config.api_key = key
                result = await routes.start_teaching_assistant(request, db, SimpleNamespace(id=1))
                self.assertTrue(result["success"])
                self.assertEqual(self.requests[-1].headers["Authorization"], "Bearer " + key)

    async def test_status_uses_admin_config_without_env_key(self):
        self.service._get_model_config = AsyncMock(return_value=self.config)
        with patch.object(routes, "get_dynamic_ai_service", return_value=self.service), patch.object(routes.settings, "AI_ENABLED", True), patch.object(routes.settings, "DASHSCOPE_API_KEY", ""):
            result = await routes.get_ai_status(db="test-db")
        self.assertEqual(result, {"enabled": True, "provider": "dashscope", "model": "test-text"})
        self.service._get_model_config.assert_awaited_once_with("test-db", model_type="text")

    async def test_status_reports_missing_model_as_unavailable(self):
        self.service._get_model_config = AsyncMock(return_value=None)
        with patch.object(routes, "get_dynamic_ai_service", return_value=self.service), patch.object(routes.settings, "AI_ENABLED", True):
            self.assertEqual(await routes.get_ai_status(db="test-db"), {"enabled": False, "provider": None, "model": None})


if __name__ == "__main__":
    unittest.main()
