"""Pipeline settings, loaded from the git-ignored `.env` (see `.env.example`)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractSettings(BaseSettings):
    """Production-MySQL access + pseudonymization pepper (D-20, D-34).

    The source DB is live and strictly read-only for this project (CLAUDE.md
    binding constraint 5); these settings only ever open read-only sessions.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    statsbot_db_host: str
    statsbot_db_port: int = 3306
    statsbot_db_name: str
    statsbot_db_user: str
    statsbot_db_password: str
    pseudonym_pepper: str
