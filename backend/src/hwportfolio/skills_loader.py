"""Seed Skill rows from the versioned taxonomy in /config/skills/."""

from __future__ import annotations

from pathlib import Path

import yaml

from .db import session_scope
from .models import Skill


def find_taxonomy_file() -> Path | None:
    # Walk up from this file to find the repo-root config/skills directory.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "skills" / "skills.v1.yaml"
        if candidate.exists():
            return candidate
    return None


def seed_skills(path: Path | None = None) -> int:
    path = path or find_taxonomy_file()
    if path is None:
        return 0
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    version = str(data.get("version", "1.0"))
    added = 0
    with session_scope() as session:
        existing = {s.key for s in session.query(Skill).all()}
        for entry in data.get("skills", []):
            if entry["key"] in existing:
                continue
            session.add(Skill(
                key=entry["key"],
                label=entry["label"],
                category=entry["category"],
                taxonomy_version=version,
            ))
            added += 1
    return added
