"""Shell helpers for shared Daytona sandboxes."""

from __future__ import annotations

import shlex


def ensure_directory_command(path: str) -> str:
    """mkdir -p with permissive mode; uses sudo fallback on shared Daytona VMs."""
    quoted = shlex.quote(path)
    return (
        f"mkdir -p {quoted} 2>/dev/null || sudo mkdir -p {quoted}; "
        f"chmod -R a+rwX {quoted} 2>/dev/null || sudo chmod -R a+rwX {quoted} 2>/dev/null || true"
    )
