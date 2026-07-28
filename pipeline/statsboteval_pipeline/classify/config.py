"""Classifier settings (Azure OpenAI EU Data Zone Standard — D-30, D-34).

Chat text leaves the machine only through this client, transiently, to the
consented Azure OpenAI EU platform; nothing is persisted cloud-side.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from statsboteval_pipeline.classify.prompts import BATCH_LIMIT, DEFAULT_BATCH_SIZE
from statsboteval_pipeline.labels import CURRENT_LABEL_VERSION


class ThemeSettings(BaseSettings):
    """The one classifier setting the offline path also needs: which reviewed
    theme set `run-weekly` should assign/aggregate. Split out so an offline
    `--skip-classify` run never requires the Azure endpoint fields."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    classifier_theme_set_version: str = "statsboteval-themes-v1"


class ClassifierSettings(ThemeSettings):
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
    # Base reasoning effort. "low" adopted at the Task-19 model decision (D-41):
    # on the 300 consensus messages it lifted average MCC .57 -> .72 over
    # "minimal", while Bergmann-shaped per-category prompts did not help.
    classifier_reasoning_effort: str = "low"
    # Messages per model call — the operating size, bounded by the prompt module's
    # ceiling. 10 adopted for statsboteval-v2 (D-45): batch size and reasoning
    # effort turned out to be one resource, and 50 left the consolidated prompt
    # (650 decisions per call) past the point where the model stops reading the
    # codebook literally. Range-checked here so a bad value fails at startup
    # rather than on the first prompt build, mid-run.
    classifier_batch_size: int = Field(default=DEFAULT_BATCH_SIZE, ge=1, le=BATCH_LIMIT)
    # Per-request timeout. The SDK default (600s) let one dead connection stall a
    # run for max_retries x 10 min; a 50-message batch normally answers in <2 min.
    classifier_timeout_seconds: float = 120.0
    # Codebook materials directory (git-ignored local files, D-16) and the label
    # bookkeeping: which version this pipeline writes, and the provenance tag
    # recorded per row (update at the Task 19 model decision).
    bergmann_prompts_dir: str | None = None
    classifier_label_version: str = CURRENT_LABEL_VERSION
    classifier_model_tag: str = "gpt-5-mini@2025-08-07"
