"""REST API и веб-интерфейс (LLM подменена)."""

import logging

from app.llm.client import LLMAuthError, LLMTimeoutError
from tests.conftest import FakeLLM, llm_reply


def test_suggest_endpoint_returns_structured_response(make_client):
    llm = FakeLLM(llm_reply())
    client = make_client(llm)
    response = client.post(
        "/api/v1/suggest",
        json={
            "message": "Сколько стоит Бриз 09?",
            "history_text": "Клиент: Здравствуйте\nМенеджер: Добрый день! Чем помочь?",
            "client_name": "Анна",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body["suggestion"]) >= {
        "customer_reply",
        "upsell_recommendation",
        "upsell_reason",
        "suggested_sales_phrase",
        "upsell_applicable",
    }
    assert body["meta"]["model"] == "fake-model"
    assert body["meta"]["request_id"]
    # история из текста разобрана на реплики
    assert "Менеджер: Добрый день! Чем помочь?" in llm.last_user_prompt


def test_structured_history_is_accepted(make_client):
    llm = FakeLLM(llm_reply())
    client = make_client(llm)
    response = client.post(
        "/api/v1/suggest",
        json={
            "message": "А монтаж?",
            "history": [{"role": "client", "text": "Беру Бриз 12"}, {"role": "manager", "text": "Отлично!"}],
        },
    )
    assert response.status_code == 200
    assert "Клиент: Беру Бриз 12" in llm.last_user_prompt


def test_validation_error_does_not_echo_input(make_client):
    client = make_client(FakeLLM())
    response = client.post("/api/v1/suggest", json={"message": "   ", "client_name": "Секретное Имя"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "Секретное Имя" not in response.text


def test_llm_timeout_maps_to_504(make_client):
    client = make_client(FakeLLM(LLMTimeoutError()))
    response = client.post("/api/v1/suggest", json={"message": "Сколько стоит монтаж?"})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "llm_timeout"


def test_llm_auth_error_maps_to_503(make_client):
    client = make_client(FakeLLM(LLMAuthError()))
    response = client.post("/api/v1/suggest", json={"message": "Сколько стоит монтаж?"})
    assert response.status_code == 503
    assert "LLM_API_KEY" in response.json()["error"]["message"]


def test_invalid_model_output_maps_to_502(make_client):
    client = make_client(FakeLLM("не json", "снова не json"))
    response = client.post("/api/v1/suggest", json={"message": "Сколько стоит монтаж?"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_invalid_output"


def test_personal_data_is_not_logged(make_client, caplog):
    caplog.set_level(logging.DEBUG)
    client = make_client(FakeLLM(llm_reply()))
    client.post(
        "/api/v1/suggest",
        json={"message": "Мой номер +7 916 555-12-34, хочу Бриз 09", "client_name": "Евлампия"},
    )
    assert "555-12-34" not in caplog.text
    assert "Евлампия" not in caplog.text
    assert "хочу Бриз 09" not in caplog.text
    assert "suggestion ready" in caplog.text


def test_health(make_client):
    body = make_client(FakeLLM()).get("/health").json()
    assert body["status"] == "ok"
    assert body["knowledge_base"]["products"] >= 5


def test_knowledge_base_endpoint(make_client):
    body = make_client(FakeLLM()).get("/api/v1/knowledge-base").json()
    assert any(p["id"] == "breeze-09" and "42 900" in p["price"] for p in body["products"])


def test_ui_and_docs_are_served(make_client):
    client = make_client(FakeLLM())
    page = client.get("/")
    assert page.status_code == 200 and "Сгенерировать рекомендации" in page.text
    assert client.get("/static/app.js").status_code == 200
    assert "/api/v1/suggest" in client.get("/openapi.json").json()["paths"]
