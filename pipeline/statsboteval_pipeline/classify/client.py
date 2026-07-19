"""Azure OpenAI client wrapper: one `complete(prompt) -> str` call.

Retry on 429/5xx uses the openai SDK's built-in capped exponential backoff
(`max_retries`), honoring `retry-after`. Deterministic settings are pinned per
D-30: `seed`, `reasoning_effort="minimal"`, a fixed `api-version`, and the
deployment name as `model`.
"""

from __future__ import annotations

from typing import Literal

import httpx
import openai

from statsboteval_pipeline.classify.config import ClassifierSettings

_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

# The effort ladder the runner may climb on format-deviation retries.
Effort = Literal["minimal", "low", "medium"]


class ClassifierClient:
    def __init__(self, settings: ClassifierSettings, *, http_client: httpx.Client | None = None) -> None:
        api_key = settings.azure_openai_api_key
        if api_key:
            token_provider = None
        else:
            # Imported lazily: only needed on the credential path.
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            token_provider = get_bearer_token_provider(DefaultAzureCredential(), _TOKEN_SCOPE)
        self._deployment = settings.azure_openai_deployment
        self._seed = settings.classifier_seed
        self._client = openai.AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            api_key=api_key,
            azure_ad_token_provider=token_provider,
            max_retries=settings.classifier_max_retries,
            timeout=settings.classifier_timeout_seconds,
            http_client=http_client,
        )

    def complete(self, prompt: str, *, reasoning_effort: Effort = "minimal") -> str:
        # "minimal" is the pinned default (D-30); the runner escalates it on
        # format-deviation retries, where more reasoning reliably restores the
        # table contract (the deviation is recorded via the retry, not hidden).
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort=reasoning_effort,
            seed=self._seed,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("empty completion from the classifier model")
        return content
