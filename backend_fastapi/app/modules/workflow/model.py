"""Scheduled workflows (single LLM task per workflow for now)."""

from __future__ import annotations

import enum
from uuid import UUID, uuid4

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.utils.datetime import datetime, now_utc


class WorkflowTaskType(str, enum.Enum):
    LLM = "llm"


class WorkflowScheduleType(str, enum.Enum):
    ONCE = "once"
    DAILY = "daily"
    INTERVAL = "interval"


class WorkflowRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Workflow(SQLModel, table=True):
    __tablename__ = "workflows"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    name: str = Field(max_length=255, nullable=False)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    task_type: WorkflowTaskType = Field(default=WorkflowTaskType.LLM, nullable=False)
    prompt: str = Field(sa_column=Column(Text, nullable=False))
    enabled: bool = Field(default=True, nullable=False)
    schedule_type: WorkflowScheduleType = Field(nullable=False, index=True)
    run_at: datetime | None = Field(default=None, nullable=True)
    run_time: str | None = Field(default=None, max_length=5, nullable=True)
    interval_minutes: int | None = Field(default=None, nullable=True)
    next_run_at: datetime | None = Field(default=None, nullable=True, index=True)
    last_run_at: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
    updated_at: datetime = Field(default_factory=now_utc, nullable=False)


class WorkflowRun(SQLModel, table=True):
    __tablename__ = "workflow_runs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workflow_id: UUID = Field(foreign_key="workflows.id", nullable=False, index=True)
    status: WorkflowRunStatus = Field(default=WorkflowRunStatus.PENDING, nullable=False, index=True)
    started_at: datetime | None = Field(default=None, nullable=True)
    finished_at: datetime | None = Field(default=None, nullable=True)
    output_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=now_utc, nullable=False)
