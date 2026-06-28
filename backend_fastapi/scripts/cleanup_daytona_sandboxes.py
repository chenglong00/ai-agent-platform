#!/usr/bin/env python3
"""Delete all Daytona sandboxes in the org to free disk quota.

Usage:
  cd backend_fastapi
  uv run python scripts/cleanup_daytona_sandboxes.py
  uv run python scripts/cleanup_daytona_sandboxes.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete all Daytona sandboxes.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List sandboxes without deleting them.",
    )
    args = parser.parse_args()

    if not settings.DAYTONA_API_KEY:
        print("DAYTONA_API_KEY is not set.", file=sys.stderr)
        return 1

    os.environ.setdefault("DAYTONA_API_KEY", settings.DAYTONA_API_KEY)
    if settings.DAYTONA_TARGET:
        os.environ.setdefault("DAYTONA_TARGET", settings.DAYTONA_TARGET)
    if settings.DAYTONA_API_URL:
        os.environ.setdefault("DAYTONA_API_URL", settings.DAYTONA_API_URL)

    from daytona import Daytona

    client = Daytona()
    sandboxes = list(client.list())
    if not sandboxes:
        print("No Daytona sandboxes found.")
        return 0

    print(f"Found {len(sandboxes)} sandbox(es):")
    for sb in sandboxes:
        sid = getattr(sb, "id", sb)
        state = getattr(sb, "state", "?")
        print(f"  - {sid} ({state})")

    if args.dry_run:
        print("Dry run — nothing deleted.")
        return 0

    deleted = 0
    for sb in sandboxes:
        sid = getattr(sb, "id", sb)
        try:
            client.delete(sb)
            deleted += 1
            print(f"Deleted {sid}")
        except Exception as exc:
            print(f"Failed to delete {sid}: {exc}", file=sys.stderr)

    print(f"Done. Deleted {deleted}/{len(sandboxes)} sandbox(es).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
