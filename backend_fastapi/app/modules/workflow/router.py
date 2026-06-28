"""Workflow create / schedule API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security.dependencies import get_db
from app.modules.auth.rbac import RequireUser
from app.modules.user.schema import UserResponse
from app.modules.workflow.schema import (
    CreateWorkflowRequest,
    DeleteWorkflowResponse,
    TriggerWorkflowResponse,
    UpdateWorkflowRequest,
    WorkflowRunSummary,
    WorkflowSummary,
)
from app.modules.workflow.service import workflow_service

router = APIRouter()


@router.get("", response_model=list[WorkflowSummary])
async def list_workflows(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[WorkflowSummary]:
    return await workflow_service.list_for_user(session, current_user.id)


@router.post("", response_model=WorkflowSummary)
async def create_workflow(
    body: CreateWorkflowRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> WorkflowSummary:
    return await workflow_service.create_workflow(session, current_user.id, body)


@router.patch("/{workflow_id}", response_model=WorkflowSummary)
async def update_workflow(
    workflow_id: UUID,
    body: UpdateWorkflowRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> WorkflowSummary:
    return await workflow_service.update_workflow(session, current_user.id, workflow_id, body)


@router.delete("/{workflow_id}", response_model=DeleteWorkflowResponse)
async def delete_workflow(
    workflow_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> DeleteWorkflowResponse:
    await workflow_service.delete_workflow(session, current_user.id, workflow_id)
    return DeleteWorkflowResponse(id=workflow_id)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunSummary])
async def list_workflow_runs(
    workflow_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> list[WorkflowRunSummary]:
    return await workflow_service.list_runs(session, current_user.id, workflow_id)


@router.post("/{workflow_id}/run", response_model=TriggerWorkflowResponse)
async def trigger_workflow(
    workflow_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(RequireUser)],
) -> TriggerWorkflowResponse:
    run = await workflow_service.trigger_run(session, current_user.id, workflow_id)
    return TriggerWorkflowResponse(run=run)
