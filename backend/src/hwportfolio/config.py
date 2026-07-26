"""Runtime configuration.

Boring on purpose: environment variables with local-dev defaults. SQLite and a
local storage directory mean a teacher-shaped laptop can run the whole stack
with zero setup; Postgres and object storage are a DATABASE_URL / STORAGE_DIR
swap away.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HWP_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./hwp.db"
    storage_dir: Path = Path("./storage")

    # Transcription provider: "mock" (default, no network), "gemini" (cheap
    # dev/testing), or "claude" (production candidate). All sit behind the
    # same TranscriptionProvider interface — GOALS §5.2, never couple to one.
    transcription_provider: str = "mock"
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"

    # Job queue: "inprocess" is the only alpha implementation. The interface in
    # jobs/queue.py is where a Redis-backed queue plugs in later.
    queue_backend: str = "inprocess"
    queue_workers: int = 2

    # Share grants (parent view) default lifetime, in hours.
    share_grant_ttl_hours: int = 72


settings = Settings()
