"""Process-wide Modal sandbox used by the deep agent.

One global sandbox is created lazily and shared across all chat threads.
Sandbox creation is expensive and requires Modal credentials, so we defer it
until the first agent invocation. Use ``reset_sandbox()`` to terminate and
recreate the sandbox (e.g. after the agent has dirtied state you don't want
to keep).

Required env vars when ``settings.DEEP_AGENT_BACKEND == "modal"``:
- ``MODAL_TOKEN_ID``
- ``MODAL_TOKEN_SECRET``
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    import modal
    from langchain_modal import ModalSandbox

logger = logging.getLogger(__name__)

_sandbox: modal.Sandbox | None = None
_backend: ModalSandbox | None = None
_lock = threading.Lock()


def _build_sandbox() -> tuple[modal.Sandbox, ModalSandbox]:
    """Create a fresh Modal sandbox + ``ModalSandbox`` backend pair."""
    # Imports are local so projects that don't enable Modal don't have to
    # install the deps in the import path of this module.
    import modal
    from langchain_modal import ModalSandbox

    app = modal.App.lookup(settings.DEEP_AGENT_MODAL_APP, create_if_missing=True)
    workdir = settings.DEEP_AGENT_SANDBOX_WORKDIR

    # A minimal image with the tools the agent typically needs. Add or remove
    # ``apt_install`` packages here as needed; e.g. add ``"nodejs", "npm"`` if
    # you want the agent to be able to run Node tooling.
    image = (
        modal.Image.debian_slim()
        .apt_install("git", "curl", "ca-certificates")
        .run_commands(f"mkdir -p {workdir}")
    )

    sandbox = modal.Sandbox.create(
        image=image,
        workdir=workdir,
        app=app,
    )
    backend = ModalSandbox(sandbox=sandbox)
    logger.info(
        "deep_agent_modal_sandbox_created sandbox_id=%s app=%s workdir=%s",
        backend.id, settings.DEEP_AGENT_MODAL_APP, workdir,
    )
    return sandbox, backend


def get_sandbox_backend() -> ModalSandbox:
    """Return the singleton ``ModalSandbox`` backend (creating it if needed)."""
    global _sandbox, _backend
    if _backend is not None:
        return _backend
    with _lock:
        if _backend is not None:
            return _backend
        _sandbox, _backend = _build_sandbox()
        return _backend


def get_sandbox() -> modal.Sandbox | None:
    """Return the underlying ``modal.Sandbox`` if one has been created."""
    return _sandbox


def reset_sandbox() -> str | None:
    """Terminate the current sandbox (if any) and rebuild on next access.

    Returns the new sandbox id, or ``None`` if rebuild failed (logged).
    """
    global _sandbox, _backend
    with _lock:
        old = _sandbox
        _sandbox = None
        _backend = None
        if old is not None:
            try:
                old.terminate()
                logger.info("deep_agent_modal_sandbox_terminated old_id=%s", old.object_id)
            except Exception:
                logger.exception("deep_agent_modal_sandbox_terminate_failed")
        try:
            _sandbox, _backend = _build_sandbox()
        except Exception:
            logger.exception("deep_agent_modal_sandbox_rebuild_failed")
            return None
        return _backend.id
