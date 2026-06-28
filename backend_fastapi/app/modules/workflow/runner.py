"""Execute a scheduled workflow run via the deep agent."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.agent.service import agent_service
from app.modules.knowledge_base.access import build_user_access_context
from app.modules.user.model import User
from app.modules.user.schema import UserResponse
from app.modules.workflow.model import Workflow, WorkflowRun, WorkflowRunStatus, WorkflowScheduleType
from app.modules.workflow.schedule import compute_next_run_at
from app.utils.datetime import now_utc

logger = logging.getLogger(__name__)


async def execute_workflow_run(
    session: AsyncSession,
    workflow: Workflow,
    run: WorkflowRun,
) -> WorkflowRun:
    """Run the workflow LLM task and persist run + workflow timestamps."""
    user = await session.get(User, workflow.user_id)
    if user is None:
        run.status = WorkflowRunStatus.FAILED
        run.error = "Workflow owner not found"
        run.finished_at = now_utc()
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run

    run.status = WorkflowRunStatus.RUNNING
    run.started_at = now_utc()
    session.add(run)
    await session.commit()

    kb_ctx = await build_user_access_context(session, UserResponse.model_validate(user))
    try:
        text, pending = await agent_service.reply(
            None,
            workflow.prompt,
            user_id=workflow.user_id,
            conversation_id=run.id,
            user_role=kb_ctx.role.value,
            group_ids=list(kb_ctx.group_ids),
        )
        if pending:
            run.status = WorkflowRunStatus.FAILED
            run.error = "Agent requested tool approval; scheduled runs cannot be interactive."
            run.output_text = text
        else:
            run.status = WorkflowRunStatus.SUCCEEDED
            run.output_text = text
    except Exception as exc:
        logger.exception("workflow_run_failed workflow_id=%s run_id=%s", workflow.id, run.id)
        run.status = WorkflowRunStatus.FAILED
        run.error = str(exc)[:4000]

    finished = now_utc()
    run.finished_at = finished
    session.add(run)

    workflow.last_run_at = finished
    if workflow.schedule_type == WorkflowScheduleType.ONCE:
        workflow.enabled = False
        workflow.next_run_at = None
    else:
        workflow.next_run_at = compute_next_run_at(
            schedule_type=workflow.schedule_type,
            enabled=workflow.enabled,
            run_at=workflow.run_at,
            run_time=workflow.run_time,
            interval_minutes=workflow.interval_minutes,
            last_run_at=finished,
            from_time=finished,
        )
    workflow.updated_at = finished
    session.add(workflow)
    await session.commit()
    await session.refresh(run)
    return run
