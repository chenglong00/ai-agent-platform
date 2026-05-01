"""Todo list tool — lets the deep agent track task progress visible to the user."""

from langchain_core.tools import tool
from pydantic import BaseModel, field_validator


_ALLOWED_STATUSES = {"pending", "in_progress", "completed"}


class TodoItem(BaseModel):
    content: str
    # Plain str (not Literal) — Gemini Vertex tends to malform tool calls when
    # tool schemas use Literal/Enum types. We validate the value at runtime.
    status: str = "pending"

    @field_validator("status")
    @classmethod
    def _normalize_status(cls, value: str) -> str:
        v = (value or "pending").strip().lower().replace("-", "_")
        return v if v in _ALLOWED_STATUSES else "pending"


@tool
def set_todos(todos: list[TodoItem]) -> str:
    """Update the task todo list visible to the user.

    Call at the START of any multi-step task with all planned steps as 'pending'.
    Update individual statuses to 'in_progress' when beginning a step and
    'completed' once it is done. Allowed statuses: pending, in_progress, completed.
    Omit trivial sub-steps; aim for 3-8 items that give the user a meaningful
    progress view.
    """
    return f"Todo list updated: {len(todos)} items"
