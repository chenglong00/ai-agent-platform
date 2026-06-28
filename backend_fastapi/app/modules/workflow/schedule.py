"""Compute next run times for workflow schedules."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.modules.workflow.model import WorkflowScheduleType

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_run_time(value: str) -> tuple[int, int]:
    match = _TIME_RE.match(value.strip())
    if not match:
        raise HTTPException(status_code=400, detail="run_time must be HH:MM (UTC)")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise HTTPException(status_code=400, detail="run_time must be a valid UTC time")
    return hour, minute


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compute_next_run_at(
    *,
    schedule_type: WorkflowScheduleType,
    enabled: bool,
    run_at: datetime | None,
    run_time: str | None,
    interval_minutes: int | None,
    last_run_at: datetime | None = None,
    from_time: datetime | None = None,
) -> datetime | None:
    """Return the next UTC run time, or None if the workflow should not run again."""
    if not enabled:
        return None

    now = _as_utc(from_time or datetime.now(timezone.utc))

    if schedule_type == WorkflowScheduleType.ONCE:
        if last_run_at is not None:
            return None
        if run_at is None:
            return None
        target = _as_utc(run_at)
        return target if target > now else None

    if schedule_type == WorkflowScheduleType.DAILY:
        if not run_time:
            return None
        hour, minute = parse_run_time(run_time)
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if schedule_type == WorkflowScheduleType.INTERVAL:
        if not interval_minutes or interval_minutes < 1:
            return None
        if last_run_at is not None:
            return _as_utc(last_run_at) + timedelta(minutes=interval_minutes)
        return now + timedelta(minutes=interval_minutes)

    return None
