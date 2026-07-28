"""Phase B Task 8: Azure OpenAI classifier client (no network — httpx mock transport)."""

import json
import os
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from statsboteval_pipeline.classify.client import ClassifierClient
from statsboteval_pipeline.classify.config import ClassifierSettings
from statsboteval_pipeline.classify.prompts import BATCH_LIMIT, DEFAULT_BATCH_SIZE


def make_settings(**overrides: Any) -> ClassifierSettings:
    values: dict[str, Any] = {
        "azure_openai_endpoint": "https://example.openai.azure.com",
        "azure_openai_api_key": "test-key",
    }
    values.update(overrides)
    return ClassifierSettings(_env_file=None, **values)


def completion_body(content: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-5-mini",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
    }


def client_with(handler: Any, settings: ClassifierSettings | None = None) -> ClassifierClient:
    settings = settings or make_settings()
    return ClassifierClient(settings, http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_missing_endpoint_raises_clear_config_error() -> None:
    with pytest.raises(ValidationError, match="azure_openai_endpoint"):
        ClassifierSettings(_env_file=None, azure_openai_api_key="k")


def test_batch_size_defaults_to_the_tuned_size_within_the_ceiling() -> None:
    # D-45 split the two roles: 10 is what we run at, BATCH_LIMIT is what no config may cross.
    assert DEFAULT_BATCH_SIZE == 10
    assert make_settings().classifier_batch_size == DEFAULT_BATCH_SIZE
    assert make_settings(classifier_batch_size=BATCH_LIMIT).classifier_batch_size == BATCH_LIMIT
    # Rejected at construction, not on the first prompt build several minutes into a run.
    for bad in (0, BATCH_LIMIT + 1):
        with pytest.raises(ValidationError, match="classifier_batch_size"):
            make_settings(classifier_batch_size=bad)


def test_complete_returns_canned_content_and_pins_settings() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=completion_body("| Message | X |"))

    client = client_with(handler)
    assert client.complete("prompt text") == "| Message | X |"
    assert "/deployments/gpt-5-mini/" in seen["url"]
    assert "api-version=" in seen["url"]
    body = seen["body"]
    assert body["model"] == "gpt-5-mini"
    assert body["reasoning_effort"] == "minimal"
    assert body["seed"] == make_settings().classifier_seed
    assert body["messages"] == [{"role": "user", "content": "prompt text"}]


def test_request_timeout_is_pinned_from_settings() -> None:
    # The SDK default of 600s once let a dead connection stall a run for ~50 min.
    client = ClassifierClient(make_settings(classifier_timeout_seconds=42.0))
    assert client._client.timeout == 42.0


def test_reasoning_effort_override_propagates() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=completion_body("ok"))

    assert client_with(handler).complete("p", reasoning_effort="medium") == "ok"
    assert seen["body"]["reasoning_effort"] == "medium"


def test_429_then_200_retries_once_and_succeeds() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "throttled"}})
        return httpx.Response(200, json=completion_body("ok"))

    assert client_with(handler).complete("p") == "ok"
    assert len(calls) == 2


def test_exhausted_retries_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "throttled"}})

    with pytest.raises(Exception):
        client_with(handler).complete("p")


@pytest.mark.skipif(
    not all(os.environ.get(v) for v in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY")),
    reason="live smoke needs AZURE_OPENAI_* exported (never set in CI)",
)
def test_live_smoke_completes() -> None:
    # Mirrors the extract live smoke: runs only on the operator machine with real env.
    client = ClassifierClient(ClassifierSettings())  # type: ignore[call-arg]
    assert client.complete("Reply with the single word OK.").strip()


def test_empty_completion_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = completion_body("x")
        body["choices"][0]["message"]["content"] = None
        return httpx.Response(200, json=body)

    with pytest.raises(RuntimeError, match="empty completion"):
        client_with(handler).complete("p")
