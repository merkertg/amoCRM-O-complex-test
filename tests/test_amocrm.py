"""Интеграция с amoCRM: вебхуки, токен виджета, адаптер (HTTP amoCRM мокается)."""

import time
from urllib.parse import urlencode

import httpx
import jwt
import pytest

from app.integrations.amocrm.client import AmoCRMClient
from app.integrations.amocrm.webhooks import extract_chat_messages, parse_nested_form
from app.schemas import Role
from tests.conftest import FakeLLM, llm_reply

SECRET = "integration-secret-key-for-tests-0123456789"
CLIENT_ID = "6f1c2c1a-1111-2222-3333-444455556666"
ACCOUNT_URL = "https://testshop.amocrm.ru"
WEBHOOK_SECRET = "hook-secret"
LEAD_ID = 1001
CONTACT_ID = 501

AMO_SETTINGS = {
    "amocrm_enabled": True,
    "amocrm_base_url": ACCOUNT_URL,
    "amocrm_access_token": "amo-token",
    "amocrm_client_id": CLIENT_ID,
    "amocrm_client_secret": SECRET,
    "amocrm_webhook_secret": WEBHOOK_SECRET,
}


def widget_token(**overrides) -> str:
    now = int(time.time())
    payload = {
        "iss": ACCOUNT_URL,
        "aud": "https://assistant.example.com",
        "jti": "0b1f6a2e-aaaa-bbbb-cccc-000000000000",
        "iat": now,
        "nbf": now,
        "exp": now + 1800,
        "account_id": 31000000,
        "user_id": 7000000,
        "client_uuid": CLIENT_ID,
        "subdomain": "testshop",
    }
    payload.update(overrides)
    return jwt.encode(payload, SECRET, algorithm="HS256")


def amocrm_api(handler=None) -> AmoCRMClient:
    def default(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer amo-token"
        if request.url.path == f"/api/v4/leads/{LEAD_ID}":
            assert request.url.params["with"] == "contacts"
            return httpx.Response(
                200,
                json={
                    "id": LEAD_ID,
                    "name": "Кондиционер в спальню",
                    "_embedded": {"contacts": [{"id": CONTACT_ID, "is_main": True}]},
                },
            )
        if request.url.path == f"/api/v4/contacts/{CONTACT_ID}":
            return httpx.Response(
                200,
                json={
                    "id": CONTACT_ID,
                    "name": "Иван Петров",
                    "first_name": "Иван",
                    "custom_fields_values": [
                        {"field_code": "PHONE", "values": [{"value": "+79161112233"}]}
                    ],
                },
            )
        return httpx.Response(404)

    return AmoCRMClient(
        base_url=ACCOUNT_URL, access_token="amo-token", transport=httpx.MockTransport(handler or default)
    )


def webhook_body(entity: str, idx: int, text: str, created_at: int, msg_id: str) -> dict[str, str]:
    prefix = f"{entity}[add][{idx}]"
    return {
        f"{prefix}[id]": msg_id,
        f"{prefix}[chat_id]": "chat-uuid",
        f"{prefix}[talk_id]": "77",
        f"{prefix}[contact_id]": str(CONTACT_ID),
        f"{prefix}[text]": text,
        f"{prefix}[created_at]": str(created_at),
        f"{prefix}[element_type]": "2",
        f"{prefix}[element_id]": str(LEAD_ID),
        "account[subdomain]": "testshop",
    }


def post_webhook(client, body: dict[str, str], secret: str = WEBHOOK_SECRET):
    return client.post(
        f"/api/v1/amocrm/webhook?secret={secret}",
        content=urlencode(body),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


@pytest.fixture
def llm():
    return FakeLLM(llm_reply())


@pytest.fixture
def client(make_client, llm):
    return make_client(llm, amocrm_client=amocrm_api(), **AMO_SETTINGS)


def seed_dialog(client):
    now = int(time.time())
    post_webhook(client, webhook_body("message", 0, "Здравствуйте, нужен кондиционер в спальню", now - 300, "m1"))
    post_webhook(client, webhook_body("outgoing_message", 0, "Добрый день! Какая площадь?", now - 200, "m2"))
    post_webhook(client, webhook_body("message", 0, "18 метров.", now - 100, "m3"))
    post_webhook(client, webhook_body("message", 0, "Сколько стоит с установкой?", now - 90, "m4"))


# ---------- Разбор вебхуков ----------


def test_parse_nested_form():
    data = parse_nested_form([("message[add][0][text]", "Привет"), ("account[id]", "1")])
    assert data == {"message": {"add": {"0": {"text": "Привет"}}}, "account": {"id": "1"}}


def test_extract_incoming_and_outgoing_messages():
    body = {**webhook_body("message", 0, "Вопрос", 100, "a"), **webhook_body("outgoing_message", 0, "Ответ", 200, "b")}
    messages = extract_chat_messages(parse_nested_form(body.items()))
    assert [(m.role, m.text, m.lead_id, m.contact_id) for m in messages] == [
        (Role.CLIENT, "Вопрос", LEAD_ID, CONTACT_ID),
        (Role.MANAGER, "Ответ", LEAD_ID, CONTACT_ID),
    ]


def test_webhook_rejects_wrong_secret(client):
    response = post_webhook(client, webhook_body("message", 0, "Привет", 1, "x"), secret="wrong")
    assert response.status_code == 403


def test_webhook_stores_messages_once(client):
    body = webhook_body("message", 0, "Привет", int(time.time()), "dup-1")
    assert post_webhook(client, body).json() == {"received": 1, "stored": 1}
    assert post_webhook(client, body).json() == {"received": 1, "stored": 0}  # повторная доставка


# ---------- Вызов из виджета ----------


def test_widget_suggest_builds_context_from_webhooks(client, llm):
    seed_dialog(client)
    response = client.post(
        "/api/v1/amocrm/suggest",
        json={"lead_id": LEAD_ID},
        headers={"X-Auth-Token": widget_token()},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["context"] == {
        "lead_id": LEAD_ID,
        "message_source": "webhook",
        "history_messages": 2,
        "crm_data_loaded": True,
    }
    prompt = llm.last_user_prompt
    # два последних сообщения клиента подряд — одно обращение
    assert "<customer_message>\n18 метров.\nСколько стоит с установкой?\n</customer_message>" in prompt
    assert "Менеджер: Добрый день! Какая площадь?" in prompt
    assert "Имя клиента: Иван" in prompt
    # телефон и фамилия контакта не передаются в LLM
    assert "79161112233" not in prompt and "Петров" not in prompt


def test_widget_manual_message_has_priority(client, llm):
    seed_dialog(client)
    response = client.post(
        "/api/v1/amocrm/suggest",
        json={"lead_id": LEAD_ID, "message": "А Wi-Fi модуль есть?"},
        headers={"X-Auth-Token": widget_token()},
    )
    assert response.json()["context"]["message_source"] == "manual"
    assert "<customer_message>\nА Wi-Fi модуль есть?\n</customer_message>" in llm.last_user_prompt


@pytest.mark.parametrize(
    "token",
    [
        None,
        "not-a-jwt",
        widget_token(exp=int(time.time()) - 3600),
        widget_token(client_uuid="another-integration"),
        widget_token(iss="https://evil.amocrm.ru"),
        jwt.encode({"account_id": 1, "user_id": 1, "iat": 1, "exp": int(time.time()) + 60}, "wrong-secret-0123456789abcdefghijk", algorithm="HS256"),
    ],
)
def test_widget_rejects_invalid_tokens(client, token):
    headers = {"X-Auth-Token": token} if token else {}
    response = client.post("/api/v1/amocrm/suggest", json={"lead_id": LEAD_ID}, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "amocrm_widget_unauthorized"


def test_widget_without_messages_asks_to_paste_text(client):
    response = client.post(
        "/api/v1/amocrm/suggest", json={"lead_id": LEAD_ID}, headers={"X-Auth-Token": widget_token()}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "amocrm_no_message"


def test_widget_works_when_amocrm_api_is_down(make_client, llm):
    def down(request):
        raise httpx.ConnectError("down", request=request)

    client = make_client(llm, amocrm_client=amocrm_api(down), **AMO_SETTINGS)
    response = client.post(
        "/api/v1/amocrm/suggest",
        json={"lead_id": LEAD_ID, "message": "Сколько стоит монтаж?"},
        headers={"X-Auth-Token": widget_token()},
    )
    assert response.status_code == 200
    assert response.json()["context"]["crm_data_loaded"] is False
    assert any("amoCRM" in w for w in response.json()["meta"]["warnings"])


def test_unknown_lead_returns_404(make_client, llm):
    client = make_client(llm, amocrm_client=amocrm_api(lambda r: httpx.Response(204)), **AMO_SETTINGS)
    response = client.post(
        "/api/v1/amocrm/suggest",
        json={"lead_id": 999, "message": "Привет"},
        headers={"X-Auth-Token": widget_token()},
    )
    assert response.status_code == 404


def test_amocrm_endpoints_disabled_by_default(make_client, llm):
    client = make_client(llm)
    assert client.post("/api/v1/amocrm/suggest", json={"lead_id": 1}).status_code == 503
    assert post_webhook(client, {}).status_code == 503
