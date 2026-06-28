"""Workflow CRUD and scheduling helpers."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.workflow.model import (
    Workflow,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowScheduleType,
    WorkflowTaskType,
)
from app.modules.workflow.schedule import compute_next_run_at, parse_run_time
from app.modules.workflow.schema import (
    CreateWorkflowRequest,
    UpdateWorkflowRequest,
    WorkflowRunSummary,
    WorkflowSummary,
)
from app.utils.datetime import now_utc


class WorkflowService:
    def _validate_schedule(self, body: CreateWorkflowRequest | UpdateWorkflowRequest) -> None:
        schedule_type = getattr(body, "schedule_type", None)
        if schedule_type is None and not isinstance(body, CreateWorkflowRequest):
            return

        st = schedule_type if isinstance(body, CreateWorkflowRequest) else body.schedule_type
        if st is None:
            return

        if st == WorkflowScheduleType.ONCE:
            run_at = body.run_at
            if run_at is None:
                raise HTTPException(status_code=400, detail="run_at is required for once schedules")
        elif st == WorkflowScheduleType.DAILY:
            if not body.run_time:
                raise HTTPException(status_code=400, detail="run_time is required for daily schedules")
            parse_run_time(body.run_time)
        elif st == WorkflowScheduleType.INTERVAL:
            if body.interval_minutes is None:
                raise HTTPException(
                    status_code=400,
                    detail="interval_minutes is required for interval schedules",
                )

    def _schedule_fields(
        self,
        *,
        schedule_type: WorkflowScheduleType,
        enabled: bool,
        run_at: datetime | None,
        run_time: str | None,
        interval_minutes: int | None,
        last_run_at: datetime | None = None,
    ) -> datetime | None:
        return compute_next_run_at(
            schedule_type=schedule_type,
            enabled=enabled,
            run_at=run_at,
            run_time=run_time,
            interval_minutes=interval_minutes,
            last_run_at=last_run_at,
        )

    async def list_for_user(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> list[WorkflowSummary]:
        statement = (
            select(Workflow)
            .where(Workflow.user_id == user_id)
            .order_by(Workflow.updated_at.desc())
        )
        result = await session.exec(statement)
        return [WorkflowSummary.model_validate(row) for row in result.all()]

    async def list_runs(
        self,
        session: AsyncSession,
        user_id: UUID,
        workflow_id: UUID,
        *,
        limit: int = 20,
    ) -> list[WorkflowRunSummary]:
        await self._require_owned(session, user_id, workflow_id)
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.workflow_id == workflow_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(max(limit, 1))
        )
        result = await session.exec(statement)
        return [WorkflowRunSummary.model_validate(row) for row in result.all()]

    async def create_workflow(
        self,
        session: AsyncSession,
        user_id: UUID,
        body: CreateWorkflowRequest,
    ) -> WorkflowSummary:
        self._validate_schedule(body)
        now = now_utc()
        next_run = self._schedule_fields(
            schedule_type=body.schedule_type,
            enabled=body.enabled,
            run_at=body.run_at,
            run_time=body.run_time,
            interval_minutes=body.interval_minutes,
        )
        row = Workflow(
            user_id=user_id,
            name=body.name.strip(),
            description=(body.description or "").strip() or None,
            task_type=WorkflowTaskType.LLM,
            prompt=body.prompt.strip(),
            enabled=body.enabled,
            schedule_type=body.schedule_type,
            run_at=body.run_at,
            run_time=body.run_time,
            interval_minutes=body.interval_minutes,
            next_run_at=next_run,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return WorkflowSummary.model_validate(row)

    async def update_workflow(
        self,
        session: AsyncSession,
        user_id: UUID,
        workflow_id: UUID,
        body: UpdateWorkflowRequest,
    ) -> WorkflowSummary:
        row = await self._require_owned(session, user_id, workflow_id)
        if body.name is not None:
            row.name = body.name.strip()
        if body.description is not None:
            row.description = body.description.strip() or None
        if body.prompt is not None:
            row.prompt = body.prompt.strip()
        if body.enabled is not None:
            row.enabled = body.enabled
        if body.schedule_type is not None:
            row.schedule_type = body.schedule_type
        if body.run_at is not None or body.schedule_type == WorkflowScheduleType.ONCE:
            if body.run_at is not None:
                row.run_at = body.run_at
        if body.run_time is not None:
            row.run_time = body.run_time
        if body.interval_minutes is not None:
            row.interval_minutes = body.interval_minutes

        merged = CreateWorkflowRequest(
            name=row.name,
            description=row.description,
            prompt=row.prompt,
            enabled=row.enabled,
            schedule_type=row.schedule_type,
            run_at=row.run_at,
            run_time=row.run_time,
            interval_minutes=row.interval_minutes,
        )
        self._validate_schedule(merged)

        row.next_run_at = self._schedule_fields(
            schedule_type=row.schedule_type,
            enabled=row.enabled,
            run_at=row.run_at,
            run_time=row.run_time,
            interval_minutes=row.interval_minutes,
            last_run_at=row.last_run_at,
        )
        row.updated_at = now_utc()
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return WorkflowSummary.model_validate(row)

    async def delete_workflow(
        self,
        session: AsyncSession,
        user_id: UUID,
        workflow_id: UUID,
    ) -> None:
        row = await self._require_owned(session, user_id, workflow_id)
        runs = await session.exec(select(WorkflowRun).where(WorkflowRun.workflow_id == workflow_id))
        for run in runs.all():
            await session.delete(run)
        await session.delete(row)
        await session.commit()

    async def trigger_run(
        self,
        session: AsyncSession,
        user_id: UUID,
        workflow_id: UUID,
    ) -> WorkflowRunSummary:
        from app.modules.workflow.runner import execute_workflow_run

        row = await self._require_owned(session, user_id, workflow_id)
        existing = await session.exec(
            select(WorkflowRun).where(
                WorkflowRun.workflow_id == workflow_id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
        )
        if existing.first() is not None:
            raise HTTPException(status_code=409, detail="A run is already in progress")

        run = WorkflowRun(workflow_id=row.id, status=WorkflowRunStatus.PENDING)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        completed = await execute_workflow_run(session, row, run)
        return WorkflowRunSummary.model_validate(completed)

    async def list_due(self, session: AsyncSession, now: datetime) -> list[Workflow]:
        statement = (
            select(Workflow)
            .where(
                Workflow.enabled.is_(True),
                Workflow.next_run_at.is_not(None),
                Workflow.next_run_at <= now,
            )
            .order_by(Workflow.next_run_at.asc())
        )
        result = await session.exec(statement)
        return list(result.all())

    async def _require_owned(
        self,
        session: AsyncSession,
        user_id: UUID,
        workflow_id: UUID,
    ) -> Workflow:
        row = await session.get(Workflow, workflow_id)
        if row is None or row.user_id != user_id:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return row


workflow_service = WorkflowService()
