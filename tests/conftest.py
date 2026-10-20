import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.config import PROJECT_ROOT, Settings
from app.main import create_app

KB_PATH = PROJECT_ROOT / "data" / "knowledge_base.json"


class FakeLLM:
    """Подменяет LLM: отдаёт заранее заданные ответы и запоминает промпты."""

    model = "fake-model"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, dict):
            return json.dumps(response, ensure_ascii=False)
        return response

    @property
    def last_user_prompt(self) -> str:
        return self.calls[-1][-1]["content"]

    @property
    def last_system_prompt(self) -> str:
        return self.calls[-1][0]["content"]


def llm_reply(**overrides) -> dict:
    data = {
        "customer_reply": "Здравствуйте! Сплит-система «Бриз 09» стоит 42 900 ₽, монтаж — 9 900 ₽.",
        "needs_clarification": False,
        "upsell_applicable": False,
        "upsell_product_id": None,
        "upsell_recommendation": None,
        "upsell_reason": "Клиент только выбирает модель.",
        "suggested_sales_phrase": None,
    }
    data.update(overrides)
    return data


def run(coro):
    return asyncio.run(coro)


def make_settings(**overrides) -> Settings:
    values = {
        "knowledge_base_path": KB_PATH,
        "llm_api_key": None,
        "amocrm_enabled": False,
        "cors_allow_origins": "",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def make_client():
    """Фабрика TestClient с фейковым LLM: make_client(fake_llm, **settings)."""

    def factory(llm, amocrm_client=None, **overrides) -> TestClient:
        app = create_app(make_settings(**overrides), llm_client=llm, amocrm_client=amocrm_client)
        return TestClient(app)

    return factory
