"""Background poll loop for due workflows."""

from __future__ import annotations

import asyncio
import logging

from sqlmodel import select

from app.core.config import settings
from app.core.db.postgres import get_async_session_factory
from app.modules.workflow.model import WorkflowRun, WorkflowRunStatus
from app.modules.workflow.runner import execute_workflow_run
from app.modules.workflow.service import workflow_service
from app.utils.datetime import now_utc

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task[None] | None = None


async def _process_due_workflows() -> int:
    if not settings.WORKFLOW_SCHEDULER_ENABLED:
        return 0

    factory = get_async_session_factory()
    processed = 0
    async with factory() as session:
        due = await workflow_service.list_due(session, now_utc())
        for workflow in due:
            running = await session.exec(
                select(WorkflowRun).where(
                    WorkflowRun.workflow_id == workflow.id,
                    WorkflowRun.status == WorkflowRunStatus.RUNNING,
                )
            )
            if running.first() is not None:
                continue

            run = WorkflowRun(workflow_id=workflow.id, status=WorkflowRunStatus.PENDING)
            session.add(run)
            await session.commit()
            await session.refresh(run)
            await execute_workflow_run(session, workflow, run)
            processed += 1
            logger.info(
                "workflow_scheduled_run_completed workflow_id=%s run_id=%s status=%s",
                workflow.id,
                run.id,
                run.status.value,
            )
    return processed


async def _scheduler_loop() -> None:
    interval = max(settings.WORKFLOW_SCHEDULER_POLL_SECONDS, 15)
    while True:
        await asyncio.sleep(interval)
        try:
            count = await _process_due_workflows()
            if count:
                logger.info("workflow_scheduler_tick processed=%s", count)
        except Exception:
            logger.exception("workflow_scheduler_tick_failed")


def start_workflow_scheduler() -> None:
    global _scheduler_task
    if not settings.WORKFLOW_SCHEDULER_ENABLED:
        return
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info(
        "workflow_scheduler_started poll_s=%s",
        settings.WORKFLOW_SCHEDULER_POLL_SECONDS,
    )


async def stop_workflow_scheduler() -> None:
    global _scheduler_task
    task = _scheduler_task
    _scheduler_task = None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
