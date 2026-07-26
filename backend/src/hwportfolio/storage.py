"""Artifact storage. Local filesystem for the alpha; only URIs go in the DB.

The URI scheme keeps the DB portable: swap this module for an S3/GCS
implementation without touching any table.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .config import settings


def _root() -> Path:
    root = Path(settings.storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_bytes(data: bytes, suffix: str = ".png") -> str:
    name = f"{uuid.uuid4().hex}{suffix}"
    path = _root() / name
    path.write_bytes(data)
    return f"local://{name}"


def store_file(src: Path) -> str:
    name = f"{uuid.uuid4().hex}{src.suffix.lower() or '.png'}"
    shutil.copyfile(src, _root() / name)
    return f"local://{name}"


def resolve(uri: str) -> Path:
    if uri.startswith("local://"):
        return _root() / uri[len("local://"):]
    raise ValueError(f"Unsupported artifact URI scheme: {uri}")
