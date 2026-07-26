"""Test fixtures. Environment is configured BEFORE any hwportfolio import —
settings and the engine are created at import time.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="hwp-test-"))
os.environ["HWP_DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["HWP_STORAGE_DIR"] = str(_TMP / "storage")
os.environ["HWP_TRANSCRIPTION_PROVIDER"] = "mock"
os.environ["HWP_QUEUE_WORKERS"] = "1"

import pytest  # noqa: E402

from hwportfolio.db import engine, init_db  # noqa: E402
from hwportfolio.models import Base  # noqa: E402
from hwportfolio.skills_loader import seed_skills  # noqa: E402
from hwportfolio.transcribe.mock import MockProvider  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    init_db()
    seed_skills()
    MockProvider.clear_ground_truth()
    yield
