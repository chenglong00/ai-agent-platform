"""Build the deepagents backend that the agent should use.

Backend choice is driven by ``settings.DEEP_AGENT_BACKEND`` (see
:func:`app.ai.backend.active_backend`):

- ``"local"`` (default): :class:`LocalShellBackend` rooted at the local
  workspace directory. Filesystem tools are confined to that root via
  ``virtual_mode=True``; shell ``execute`` inherits the parent process env so
  ``PATH`` / ``HOME`` / etc. are available.
- ``"modal"``: a process-wide Modal sandbox (one global, shared by all chats).
  Requires ``MODAL_TOKEN_ID`` and ``MODAL_TOKEN_SECRET`` in the environment.
"""

from __future__ import annotations

import logging

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import BackendProtocol

from app.ai.backend import active_backend
from app.ai.backend.workspace_paths import WORKSPACE_DIR, ensure_workspace
from app.core.config import settings

logger = logging.getLogger(__name__)


def build_backend() -> BackendProtocol:
    """Return a backend instance matching ``settings.DEEP_AGENT_BACKEND``."""
    if active_backend() == "modal":
        # Imported lazily so projects that don't enable Modal don't pay the
        # import cost or need credentials at startup.
        from app.ai.backend.sandbox import get_sandbox_backend

        backend = get_sandbox_backend()
        logger.info(
            "deep_agent_backend_selected backend=modal sandbox_id=%s workdir=%s",
            backend.id, settings.DEEP_AGENT_SANDBOX_WORKDIR,
        )
        return backend

    ensure_workspace()
    backend = LocalShellBackend(
        root_dir=str(WORKSPACE_DIR),
        # Confine read/write/edit/ls/glob/grep tools to the workspace; block `..`
        # and absolute paths that would escape it. (Shell `execute` is NOT
        # restricted by virtual_mode — that's an upstream limitation.)
        virtual_mode=True,
        # Inherit the parent process env so shell commands have a working PATH,
        # HOME, etc. Without this, ``LocalShellBackend`` runs with an empty env
        # and tools like npm/node/git/mkdir misbehave (and the model often
        # hallucinates "read-only filesystem" type errors).
        inherit_env=True,
    )
    logger.info(
        "deep_agent_backend_selected backend=local workspace=%s", WORKSPACE_DIR
    )
    return backend
