#!/usr/bin/env python3
"""Migrate Daytona data from /workspace/home/{slug}/ to /home/{slug}/.

If you previously used DEEP_AGENT_SANDBOX_HOME_ROOT=/workspace/home, run this once
after switching back to /home so existing files appear in the workspace UI.

Usage:
  cd backend_fastapi
  uv run python scripts/migrate_daytona_home_paths.py --dry-run --all-users
  uv run python scripts/migrate_daytona_home_paths.py --all-users --scan-legacy-home
  uv run python scripts/migrate_daytona_home_paths.py --slug application_owner_ebee36f1
  uv run python scripts/migrate_daytona_home_paths.py --all-users --delete-legacy
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai.chat_agent.sandbox_paths import remote_sandbox_paths, sandbox_user_slug  # noqa: E402
from app.ai.chat_agent.sandbox_shell import ensure_directory_command  # noqa: E402
from app.core.config import settings  # noqa: E402

# Previous intermediate layout when /home was not pre-created with sudo.
LEGACY_HOME_ROOT = "/workspace/home"


def _apply_daytona_env() -> None:
    if settings.DAYTONA_API_KEY:
        os.environ.setdefault("DAYTONA_API_KEY", settings.DAYTONA_API_KEY)
    if settings.DAYTONA_TARGET:
        os.environ.setdefault("DAYTONA_TARGET", settings.DAYTONA_TARGET)
    if settings.DAYTONA_API_URL:
        os.environ.setdefault("DAYTONA_API_URL", settings.DAYTONA_API_URL)


def _connect_shared_daytona() -> Any:
    _apply_daytona_env()
    from daytona import Daytona
    from langchain_daytona import DaytonaSandbox

    client = Daytona()
    sandbox_id = settings.DAYTONA_SANDBOX_ID.strip()
    if sandbox_id:
        raw = client.get(sandbox_id)
        print(f"Using Daytona sandbox {sandbox_id}")
    else:
        sandboxes = list(client.list())
        if not sandboxes:
            raise RuntimeError("No Daytona sandboxes found. Set DAYTONA_SANDBOX_ID or create one.")
        raw = sandboxes[0]
        print(f"Using first Daytona sandbox {getattr(raw, 'id', raw)}")

    inner = DaytonaSandbox(sandbox=raw)
    home_base = settings.DEEP_AGENT_SANDBOX_HOME_ROOT.rstrip("/") or "/home"
    inner.execute(ensure_directory_command(home_base))
    return inner


def _sandbox_execute(inner: Any, command: str) -> tuple[int | None, str]:
    result = inner.execute(command)
    return result.exit_code, (result.output or "").strip()


def _parse_json_line(output: str) -> dict[str, Any]:
    text = output.strip()
    if not text:
        return {}
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return json.loads(text)


def _scan_legacy_slugs(inner: Any, legacy_root: str) -> list[str]:
    code = f"""
import json, os
root = {legacy_root!r}
slugs = []
if os.path.isdir(root):
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path) and not name.startswith("."):
            slugs.append(name)
print(json.dumps({{"slugs": slugs}}))
"""
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
    runner = f"import base64; exec(base64.b64decode('{encoded}').decode())"
    command = (
        f"python3 -c {json.dumps(runner)} 2>/dev/null "
        f"|| python -c {json.dumps(runner)} 2>/dev/null"
    )
    _, output = _sandbox_execute(inner, command)
    data = _parse_json_line(output)
    return [str(s) for s in data.get("slugs", [])]


def _run_python_in_sandbox(inner: Any, source: str) -> tuple[int | None, str]:
    encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
    runner = f"import base64; exec(base64.b64decode('{encoded}').decode())"
    command = (
        f"python3 -c {json.dumps(runner)} 2>/dev/null "
        f"|| python -c {json.dumps(runner)} 2>/dev/null"
    )
    return _sandbox_execute(inner, command)


def _migrate_slug(
    inner: Any,
    slug: str,
    *,
    dry_run: bool,
    delete_legacy: bool,
) -> dict[str, Any]:
    old_root = f"{LEGACY_HOME_ROOT.rstrip('/')}/{slug}"
    new_root = f"{settings.DEEP_AGENT_SANDBOX_HOME_ROOT.rstrip('/')}/{slug}"

    inspect_py = f"""
import json, os
old_root = {old_root!r}
new_root = {new_root!r}
print(json.dumps({{
    "old_exists": os.path.isdir(old_root),
    "files_found": sum(len(files) for _, _, files in os.walk(old_root)) if os.path.isdir(old_root) else 0,
    "new_exists": os.path.isdir(new_root),
}}))
"""
    _, count_out = _run_python_in_sandbox(inner, inspect_py)
    try:
        stats = _parse_json_line(count_out)
    except json.JSONDecodeError:
        return {"slug": slug, "error": f"could not inspect {old_root}: {count_out[:240]}"}

    result: dict[str, Any] = {
        "slug": slug,
        "old_root": old_root,
        "new_root": new_root,
        "old_exists": bool(stats.get("old_exists")),
        "files_found": int(stats.get("files_found", 0) or 0),
        "files_copied": 0,
        "files_skipped": 0,
        "deleted_legacy": False,
        "errors": [],
    }
    if not result["old_exists"]:
        return result
    if dry_run:
        return result

    _sandbox_execute(inner, ensure_directory_command(new_root))
    copy_cmd = (
        f"cp -a {shlex.quote(old_root)}/. {shlex.quote(new_root)}/ 2>&1 "
        f"&& chmod -R a+rwX {shlex.quote(new_root)} 2>/dev/null "
        f"|| sudo chmod -R a+rwX {shlex.quote(new_root)} 2>/dev/null || true"
    )
    exit_code, copy_out = _sandbox_execute(inner, copy_cmd)
    if exit_code not in (0, None):
        result["errors"].append(copy_out or f"cp failed with exit {exit_code}")
        return result

    after_py = f"""
import json, os
new_root = {new_root!r}
print(json.dumps({{
    "files_copied": sum(len(files) for _, _, files in os.walk(new_root)) if os.path.isdir(new_root) else 0,
}}))
"""
    _, after_out = _run_python_in_sandbox(inner, after_py)
    try:
        after = _parse_json_line(after_out)
        result["files_copied"] = int(after.get("files_copied", result["files_found"]) or 0)
    except json.JSONDecodeError:
        result["files_copied"] = result["files_found"]

    if delete_legacy and not result["errors"]:
        del_cmd = f"rm -rf {shlex.quote(old_root)}"
        del_exit, del_out = _sandbox_execute(inner, del_cmd)
        if del_exit not in (0, None):
            result["errors"].append(del_out or f"delete failed with exit {del_exit}")
        else:
            result["deleted_legacy"] = True
    return result


async def _slugs_from_postgres() -> list[str]:
    from sqlmodel import select

    from app.core.db.postgres import get_async_session_factory, init_engine
    from app.modules.user.model import User

    await init_engine()
    factory = get_async_session_factory()
    slugs: list[str] = []
    async with factory() as session:
        result = await session.exec(select(User))
        for user in result.all():
            slug = sandbox_user_slug(
                str(user.id),
                email=user.email,
                display_name=user.display_name,
            )
            slugs.append(slug)
            paths = remote_sandbox_paths(
                str(user.id),
                email=user.email,
                display_name=user.display_name,
            )
            print(f"  user {user.email} -> {slug} -> {paths.workspace}")
    return sorted(set(slugs))


def _print_result(result: dict[str, Any], *, dry_run: bool) -> None:
    slug = result.get("slug", "?")
    if result.get("error"):
        print(f"[{slug}] ERROR: {result['error']}")
        return
    if not result.get("old_exists"):
        print(f"[{slug}] nothing at {result.get('old_root')} — skipped")
        return
    found = result.get("files_found", 0)
    if dry_run:
        print(f"[{slug}] would migrate {found} file(s): {result.get('old_root')} -> {result.get('new_root')}")
        return
    copied = result.get("files_copied", 0)
    skipped = result.get("files_skipped", 0)
    print(
        f"[{slug}] copied {copied}, skipped {skipped} (already present), "
        f"found {found} -> {result.get('new_root')}"
    )
    if result.get("deleted_legacy"):
        print(f"[{slug}] removed legacy directory {result.get('old_root')}")
    for err in result.get("errors") or []:
        print(f"[{slug}] warning: {err}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy /workspace/home/{slug}/ data into /home/{slug}/ on Daytona.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be copied without changing files.",
    )
    parser.add_argument(
        "--all-users",
        action="store_true",
        help="Migrate slugs for every user in Postgres.",
    )
    parser.add_argument(
        "--scan-legacy-home",
        action="store_true",
        help="Also include slugs discovered under the legacy source root on the VM.",
    )
    parser.add_argument(
        "--slug",
        action="append",
        default=[],
        metavar="SLUG",
        help="Migrate a specific slug (repeatable).",
    )
    parser.add_argument(
        "--delete-legacy",
        action="store_true",
        help="Remove the legacy source directory after a successful copy.",
    )
    args = parser.parse_args()

    if settings.DEEP_AGENT_BACKEND.strip().lower() != "daytona":
        print("DEEP_AGENT_BACKEND is not daytona — this script only applies to Daytona.", file=sys.stderr)
        return 1
    if not settings.DAYTONA_API_KEY:
        print("DAYTONA_API_KEY is not set.", file=sys.stderr)
        return 1

    slugs: set[str] = set(args.slug)
    if args.all_users:
        print("Resolving slugs from Postgres users:")
        slugs.update(asyncio.run(_slugs_from_postgres()))

    inner = _connect_shared_daytona()
    if args.scan_legacy_home or (not slugs and not args.all_users):
        discovered = _scan_legacy_slugs(inner, LEGACY_HOME_ROOT)
        if discovered:
            print(f"Legacy {LEGACY_HOME_ROOT} slugs on VM: {', '.join(discovered)}")
        slugs.update(discovered)

    if not slugs:
        print("No slugs to migrate.")
        return 0

    print(
        f"\n{'Dry run — ' if args.dry_run else ''}"
        f"Migrating {len(slugs)} slug(s) "
        f"from {LEGACY_HOME_ROOT}/{{slug}}/ to "
        f"{settings.DEEP_AGENT_SANDBOX_HOME_ROOT.rstrip('/')}/{{slug}}/\n"
    )

    errors = 0
    for slug in sorted(slugs):
        result = _migrate_slug(
            inner,
            slug,
            dry_run=args.dry_run,
            delete_legacy=args.delete_legacy and not args.dry_run,
        )
        _print_result(result, dry_run=args.dry_run)
        if result.get("error") or result.get("errors"):
            errors += 1

    if args.dry_run:
        print("\nDry run complete — re-run without --dry-run to apply.")
    elif errors:
        print(f"\nFinished with {errors} slug(s) reporting errors.")
        return 1
    else:
        print("\nMigration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
