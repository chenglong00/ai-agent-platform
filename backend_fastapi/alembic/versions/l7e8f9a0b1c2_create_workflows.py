"""create workflows tables

Revision ID: l7e8f9a0b1c2
Revises: k6d7e8f9a0b1
Create Date: 2026-06-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "k6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_type", sa.String(length=32), nullable=False),
        sa.Column("run_at", sa.DateTime(), nullable=True),
        sa.Column("run_time", sa.String(length=5), nullable=True),
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflows_user_id"), "workflows", ["user_id"], unique=False)
    op.create_index(op.f("ix_workflows_schedule_type"), "workflows", ["schedule_type"], unique=False)
    op.create_index(op.f("ix_workflows_next_run_at"), "workflows", ["next_run_at"], unique=False)

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_runs_workflow_id"), "workflow_runs", ["workflow_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_status"), "workflow_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_runs_status"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_workflow_id"), table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index(op.f("ix_workflows_next_run_at"), table_name="workflows")
    op.drop_index(op.f("ix_workflows_schedule_type"), table_name="workflows")
    op.drop_index(op.f("ix_workflows_user_id"), table_name="workflows")
    op.drop_table("workflows")
