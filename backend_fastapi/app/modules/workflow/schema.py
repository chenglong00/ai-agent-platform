"""Workflow API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.workflow.model import (
    WorkflowRunStatus,
    WorkflowScheduleType,
    WorkflowTaskType,
)


class WorkflowSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    task_type: WorkflowTaskType
    prompt: str
    enabled: bool
    schedule_type: WorkflowScheduleType
    run_at: datetime | None
    run_time: str | None
    interval_minutes: int | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkflowRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    status: WorkflowRunStatus
    started_at: datetime | None
    finished_at: datetime | None
    output_text: str | None
    error: str | None
    created_at: datetime


class CreateWorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    prompt: str = Field(..., min_length=1, max_length=32000)
    enabled: bool = True
    schedule_type: WorkflowScheduleType
    run_at: datetime | None = None
    run_time: str | None = Field(default=None, max_length=5)
    interval_minutes: int | None = Field(default=None, ge=5, le=60 * 24 * 7)


class UpdateWorkflowRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    prompt: str | None = Field(default=None, min_length=1, max_length=32000)
    enabled: bool | None = None
    schedule_type: WorkflowScheduleType | None = None
    run_at: datetime | None = None
    run_time: str | None = Field(default=None, max_length=5)
    interval_minutes: int | None = Field(default=None, ge=5, le=60 * 24 * 7)


class DeleteWorkflowResponse(BaseModel):
    id: UUID
    deleted: bool = True


class TriggerWorkflowResponse(BaseModel):
    run: WorkflowRunSummary
