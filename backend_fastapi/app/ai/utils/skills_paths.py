"""Single source of truth for the deep agent's skills directory.

Used by:
- ``app.ai.agents.deep_agent`` to load skill packs handed to ``create_deep_agent``.

The path is anchored to this file's location so it's stable regardless of the
process's cwd. Skill packs live at ``backend_fastapi/app/ai/skills/`` (a
sibling of this ``utils/`` package).
"""

from __future__ import annotations

from pathlib import Path

SKILLS_DIR: Path = (Path(__file__).resolve().parent.parent / "skills").resolve()


def ensure_skills() -> Path:
    """Create the skills directory if missing and return its absolute path."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    return SKILLS_DIR


def resolve_within_skills(rel_path: str) -> Path:
    """Resolve a relative path strictly inside the skills directory.

    Raises ValueError on traversal (``..``), absolute paths, or anything that
    would escape ``SKILLS_DIR``.
    """
    cleaned = (rel_path or "").strip().lstrip("/")
    if cleaned in {"", "."}:
        return SKILLS_DIR

    candidate = (SKILLS_DIR / cleaned).resolve()
    try:
        candidate.relative_to(SKILLS_DIR)
    except ValueError as exc:
        raise ValueError("path escapes skills root") from exc
    return candidate
