"""OpenAI-совместимый клиент: ретраи, таймауты, ошибки провайдера (HTTP мокается)."""

import json
import logging

import httpx
import pytest

from app.llm.client import (
    LLMAuthError,
    LLMBadResponseError,
    LLMRequestError,
    LLMTimeoutError,
    LLMUnavailableError,
    OpenAICompatibleClient,
)
from tests.conftest import run

MESSAGES = [{"role": "user", "content": "Привет"}]


def ok_response(content: str = '{"customer_reply": "ok"}') -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


def make_client(handler, **kwargs) -> tuple[OpenAICompatibleClient, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request, len(requests))

    params = {
        "base_url": "https://llm.test/v1",
        "model": "test-model",
        "api_key": "sk-test-secret-key",
        "max_retries": 2,
        "backoff_seconds": 0,
    }
    params.update(kwargs)
    return OpenAICompatibleClient(transport=httpx.MockTransport(wrapped), **params), requests


def test_successful_completion_and_payload():
    client, requests = make_client(lambda req, n: ok_response())
    assert run(client.complete(MESSAGES)) == '{"customer_reply": "ok"}'

    request = requests[0]
    assert request.url == "https://llm.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer sk-test-secret-key"
    payload = json.loads(request.content)
    assert payload["model"] == "test-model"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0.2
    assert "max_tokens" not in payload


def test_optional_parameters_can_be_disabled():
    client, requests = make_client(
        lambda req, n: ok_response(), temperature=None, json_mode=False, api_key=None
    )
    run(client.complete(MESSAGES))
    payload = json.loads(requests[0].content)
    assert "temperature" not in payload and "response_format" not in payload
    assert "Authorization" not in requests[0].headers


def test_server_error_is_retried():
    client, requests = make_client(lambda req, n: httpx.Response(502) if n == 1 else ok_response())
    assert run(client.complete(MESSAGES))
    assert len(requests) == 2


def test_rate_limit_exhausts_retries():
    client, requests = make_client(lambda req, n: httpx.Response(429))
    with pytest.raises(LLMUnavailableError):
        run(client.complete(MESSAGES))
    assert len(requests) == 3


def test_timeout_is_retried_then_reported():
    def handler(req, n):
        raise httpx.ReadTimeout("timeout", request=req)

    client, requests = make_client(handler)
    with pytest.raises(LLMTimeoutError):
        run(client.complete(MESSAGES))
    assert len(requests) == 3


def test_network_error_is_reported_as_unavailable():
    def handler(req, n):
        raise httpx.ConnectError("refused", request=req)

    client, _ = make_client(handler, max_retries=0)
    with pytest.raises(LLMUnavailableError):
        run(client.complete(MESSAGES))


def test_auth_error_is_not_retried():
    client, requests = make_client(lambda req, n: httpx.Response(401, json={"error": "bad key"}))
    with pytest.raises(LLMAuthError):
        run(client.complete(MESSAGES))
    assert len(requests) == 1


def test_bad_request_is_not_retried():
    client, requests = make_client(lambda req, n: httpx.Response(400, json={"error": "unknown model"}))
    with pytest.raises(LLMRequestError):
        run(client.complete(MESSAGES))
    assert len(requests) == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>gateway</html>"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
        httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]}),
    ],
)
def test_malformed_provider_response(response):
    client, _ = make_client(lambda req, n: response)
    with pytest.raises(LLMBadResponseError):
        run(client.complete(MESSAGES))


def test_secrets_and_prompt_are_not_logged(caplog):
    caplog.set_level(logging.DEBUG)
    client, _ = make_client(lambda req, n: httpx.Response(500) if n == 1 else ok_response())
    run(client.complete([{"role": "user", "content": "Мой телефон +7 916 000-00-00"}]))
    assert "sk-test-secret-key" not in caplog.text
    assert "916" not in caplog.text
