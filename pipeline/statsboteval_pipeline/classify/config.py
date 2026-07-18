"""Classifier settings (Azure OpenAI EU Data Zone Standard — D-30, D-34).

Chat text leaves the machine only through this client, transiently, to the
consented Azure OpenAI EU platform; nothing is persisted cloud-side.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ClassifierSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_openai_endpoint: str
    azure_openai_deployment: str = "gpt-5-mini"
    azure_openai_api_version: str = "2025-04-01-preview"
    # Key-first auth: the operator lacks roleAssignments/write in MOPS (D-31), so
    # managed-identity/RBAC is unavailable; DefaultAzureCredential is the fallback.
    azure_openai_api_key: str | None = None
    # Determinism is best-effort and recorded, not assumed (D-30): seed +
    # reasoning_effort are pinned; the exact model/version goes into provenance.
    classifier_seed: int = 20260718
    classifier_max_retries: int = 5
