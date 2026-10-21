"""Защита интерфейса HTTP Basic и лимит генераций (LLM подменена)."""

import base64

import pytest
from pydantic import ValidationError

from app.api.access import RateLimitedError, RateLimiter, credentials_match
from tests.conftest import FakeLLM, llm_reply, make_settings
from tests.test_amocrm import AMO_SETTINGS, LEAD_ID, amocrm_api, widget_token

AUTH = {"ui_basic_auth_username": "manager", "ui_basic_auth_password": "s3cret-pass"}


def basic(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ---------- HTTP Basic ----------


@pytest.mark.parametrize("path", ["/", "/static/app.js", "/docs", "/openapi.json", "/api/v1/knowledge-base"])
def test_protected_paths_require_login(make_client, path):
    client = make_client(FakeLLM(), **AUTH)
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic ")
    assert response.json()["error"]["code"] == "unauthorized"
    assert client.get(path, headers=basic("manager", "s3cret-pass")).status_code == 200


def test_suggest_requires_login(make_client):
    client = make_client(FakeLLM(llm_reply()), **AUTH)
    body = {"message": "Сколько стоит Бриз 09?"}
    assert client.post("/api/v1/suggest", json=body).status_code == 401
    assert client.post("/api/v1/suggest", json=body, headers=basic("manager", "wrong")).status_code == 401
    assert client.post("/api/v1/suggest", json=body, headers=basic("manager", "s3cret-pass")).status_code == 200


def test_health_stays_public(make_client):
    assert make_client(FakeLLM(), **AUTH).get("/health").status_code == 200


def test_amocrm_endpoints_keep_their_own_auth(make_client):
    client = make_client(FakeLLM(llm_reply()), amocrm_client=amocrm_api(), **AUTH, **AMO_SETTINGS)
    response = client.post(
        "/api/v1/amocrm/suggest",
        json={"lead_id": LEAD_ID, "message": "Сколько стоит монтаж?"},
        headers={"X-Auth-Token": widget_token()},
    )
    assert response.status_code == 200  # без Basic: виджет защищён JWT


def test_login_without_password_is_rejected_at_startup():
    with pytest.raises(ValidationError, match="задаются вместе"):
        make_settings(ui_basic_auth_username="manager")


@pytest.mark.parametrize(
    "header",
    [None, "Bearer abc", "Basic !!!not-base64", "Basic " + base64.b64encode(b"no-colon").decode()],
    ids=["missing", "bearer", "not-base64", "no-colon"],
)
def test_malformed_authorization_header(header):
    assert not credentials_match(header, "manager", "s3cret-pass")


def test_password_may_contain_colon():
    assert credentials_match(basic("manager", "a:b:c")["Authorization"], "manager", "a:b:c")


# ---------- Лимит генераций ----------


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_rate_limiter_sliding_window():
    clock = Clock()
    limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)
    limiter.check("ip:a", "ip")
    limiter.check("ip:a", "ip")
    with pytest.raises(RateLimitedError) as error:
        limiter.check("ip:a", "ip")
    assert error.value.headers["Retry-After"] == "61"
    limiter.check("ip:b", "ip")  # у другого ключа свой счётчик
    clock.now += 60
    limiter.check("ip:a", "ip")  # окно сдвинулось


def test_rate_limiter_disabled_with_zero():
    limiter = RateLimiter(limit=0)
    for _ in range(100):
        limiter.check("ip:a", "ip")


def test_rate_limiter_bounds_memory():
    limiter = RateLimiter(limit=5, max_keys=3)
    for index in range(10):
        limiter.check(f"ip:{index}", "ip")
    assert list(limiter._calls) == ["ip:7", "ip:8", "ip:9"]


def test_suggest_returns_429_with_retry_after(make_client):
    client = make_client(FakeLLM(llm_reply(), llm_reply()), rate_limit_per_minute=2)
    body = {"message": "Сколько стоит Бриз 09?"}
    assert client.post("/api/v1/suggest", json=body).status_code == 200
    assert client.post("/api/v1/suggest", json=body).status_code == 200
    response = client.post("/api/v1/suggest", json=body)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) >= 1


def test_widget_limit_is_per_amocrm_user(make_client):
    client = make_client(
        FakeLLM(llm_reply(), llm_reply()), amocrm_client=amocrm_api(), rate_limit_per_minute=1, **AMO_SETTINGS
    )
    body = {"lead_id": LEAD_ID, "message": "Сколько стоит монтаж?"}
    first = client.post("/api/v1/amocrm/suggest", json=body, headers={"X-Auth-Token": widget_token(user_id=1)})
    second = client.post("/api/v1/amocrm/suggest", json=body, headers={"X-Auth-Token": widget_token(user_id=1)})
    other = client.post("/api/v1/amocrm/suggest", json=body, headers={"X-Auth-Token": widget_token(user_id=2)})
    assert (first.status_code, second.status_code, other.status_code) == (200, 429, 200)
