"""Discover and load SKILL.md files from app/ai/skills/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class SkillSummary:
    id: str
    name: str
    description: str
    path: Path


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            fields[key] = value
    return fields


def _skill_id_from_dir(path: Path) -> str | None:
    name = path.name
    if name.startswith((".", "_")):
        return None
    if not (path / "SKILL.md").is_file():
        return None
    return name


def discover_skills() -> list[SkillSummary]:
    if not SKILLS_DIR.is_dir():
        return []

    summaries: list[SkillSummary] = []
    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        skill_id = _skill_id_from_dir(entry)
        if skill_id is None:
            continue

        skill_md = entry / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        name = meta.get("name") or skill_id
        description = meta.get("description") or name
        summaries.append(
            SkillSummary(
                id=skill_id,
                name=name,
                description=description,
                path=skill_md,
            ),
        )
    return summaries


def read_skill_markdown(skill_id: str) -> str:
    normalized = skill_id.strip().strip("/")
    if not normalized or ".." in normalized or "/" in normalized:
        raise ValueError("Invalid skill id.")

    skill_dir = SKILLS_DIR / normalized
    if not _skill_id_from_dir(skill_dir):
        raise ValueError(f"Skill not found: {normalized}")

    return (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def read_builtin_skill_body(skill_id: str) -> tuple[str, str, str]:
    """Return (name, description, instruction body) for a built-in skill."""
    text = read_skill_markdown(skill_id)
    meta = _parse_frontmatter(text)
    match = _FRONTMATTER_RE.match(text)
    body = text[match.end() :].strip() if match else text.strip()
    summary = next((s for s in discover_skills() if s.id == skill_id), None)
    if summary is None:
        raise ValueError(f"Skill not found: {skill_id}")
    name = meta.get("name") or summary.name
    description = meta.get("description") or summary.description
    return name, description, body


def format_agent_skill_view(name: str, description: str, content: str) -> str:
    header = f"# {name}\n\n{description.strip()}\n\n" if description.strip() else f"# {name}\n\n"
    return header + content.strip()


def format_skills_prompt_section() -> str:
    skills = discover_skills()
    if not skills:
        return ""

    lines = [
        "Available skills — call read_skill with the skill id before following specialized workflows:",
    ]
    for skill in skills:
        lines.append(f"- {skill.id}: {skill.description}")
    return "\n".join(lines)
