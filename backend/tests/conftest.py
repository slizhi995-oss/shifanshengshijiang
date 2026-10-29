"""Never spend a developer's real search quota in automated tests."""
import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def no_live_video_search(monkeypatch):
    monkeypatch.setattr(settings, 'BOCHA_API_KEY', '')
