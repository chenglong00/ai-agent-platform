"""Application logging: human console + JSON lines for files and future cloud sinks.

**Structured record shape** (one JSON object per line when using ``JsonFormatter`` /
``JsonlFileHandler``) — stable keys for CloudWatch, Datadog, GCP, ELK, etc.::

    timestamp, level, message, logger, service_name,
    correlation_id, user_id, endpoint, status_code

Request context comes from :mod:`contextvars` (see below). ``logger.info("msg", extra={...})``
merges additional keys at the top level. File/JSONL handlers also add
``module``, ``function``, ``filename``, ``line`` when enabled.

**Extend for cloud:** attach a ``logging.Handler`` that POSTs ``structured_log_dict(record)``
to your API, or run an agent that tails ``LOG_DIR`` JSONL. No change required here
unless you add new context fields (then extend ``_record_to_log_dict`` and middleware).
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.environment import get_environment

# --- Request-scoped context (set in middleware / auth) ---------------------------------
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
endpoint_ctx: ContextVar[str | None] = ContextVar("endpoint", default=None)
status_code_ctx: ContextVar[int | None] = ContextVar("status_code", default=None)

# LogRecord keys not copied into structured ``extra`` payload
_SKIP_RECORD_KEYS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "sinfo", "message", "taskName", "request_id",
    "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process",
})

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_RESET = "\033[0m"
_DIM = "\033[2m"
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}

# Libraries that become very noisy at DEBUG when root is DEBUG
_NOISY_LIB_LOGGERS = ("httpcore", "httpx", "h11", "asyncio", "pymongo", "grpc")

# Uvicorn loggers to merge into root formatting (see ``align_uvicorn_with_root``)
_UVICORN_PROPAGATE = ("uvicorn", "uvicorn.error", "uvicorn.asgi")


def structured_log_dict(record: logging.LogRecord) -> dict[str, Any]:
    """Build the canonical structured dict for ``record`` (UTC, with callsite).

    Use from custom handlers or forwarders to cloud logging without duplicating logic.
    """
    return _record_to_log_dict(record, tz=UTC, include_callsite=True)


def _strip_ansi(message: str) -> str:
    return _ANSI_ESCAPE.sub("", message)


def _record_to_log_dict(
    record: logging.LogRecord,
    *,
    tz: datetime.tzinfo,
    message_override: str | None = None,
    service_name: str | None = None,
    include_callsite: bool = True,
) -> dict[str, Any]:
    msg = message_override if message_override is not None else record.getMessage()
    service = service_name or settings.APPLICATION_NAME
    payload: dict[str, Any] = {
        "timestamp": datetime.fromtimestamp(record.created, tz=tz).isoformat(),
        "level": record.levelname,
        "message": msg,
        "correlation_id": request_id_ctx.get(),
        "user_id": user_id_ctx.get(),
        "service_name": service,
        "endpoint": endpoint_ctx.get(),
        "status_code": status_code_ctx.get(),
        "logger": record.name,
    }
    if include_callsite:
        payload["module"] = record.module
        payload["function"] = record.funcName
        payload["filename"] = record.pathname
        payload["line"] = record.lineno
    for k, v in record.__dict__.items():
        if k not in _SKIP_RECORD_KEYS and v is not None:
            payload[k] = v
    if record.exc_info:
        payload["exception"] = logging.Formatter().formatException(record.exc_info)
    return payload


def _context_kv_strings() -> list[str]:
    out: list[str] = []
    cid = request_id_ctx.get()
    if cid is not None:
        out.append(f"correlation_id={cid}")
    uid = user_id_ctx.get()
    if uid is not None:
        out.append(f"user_id={uid}")
    ep = endpoint_ctx.get()
    if ep is not None:
        out.append(f"endpoint={ep}")
    sc = status_code_ctx.get()
    if sc is not None:
        out.append(f"status_code={sc}")
    return out


class JsonlFileHandler(logging.Handler):
    """Append one JSON line per record; **date-based** rotation (not size-based).

    **Strategy:** ``{APP_ENV}-{YYYY-MM-DD}.jsonl`` under ``LOG_DIR``, using
    ``settings.TIMEZONE`` for the calendar day. On day change, the previous file
    is closed and a new file is opened (append).

    **Limits / production:** No automatic **retention** or **compression** — add
    ``logrotate``, a cron job, or lifecycle rules on the bucket if you ship these
    files off-host. **Multi-process** (several Uvicorn/Gunicorn workers) all append
    to the **same** daily path without cross-process locking; lines can interleave
    or rarely corrupt on concurrent writes. Prefer **stdout + container log
    driver**, **one file per PID** (custom handler), or a **QueueHandler** + single
    writer process for heavy multi-worker JSONL.

    **Performance:** One ``threading.Lock`` per ``emit`` serializes writes; high
    volume may bottleneck. ``buffering=1`` line-buffers each record (safer on
    crash, more syscalls than a multi-KB buffer).
    """

    def __init__(self, base_log_dir: Path) -> None:
        super().__init__()
        self.base_log_dir = base_log_dir
        self._tz = ZoneInfo(settings.TIMEZONE)
        self._env_slug = get_environment().value
        self._current_path: Path | None = None
        self._current_date: datetime.date | None = None
        self._file: Any = None
        self._lock = threading.Lock()

    def _rotate_if_new_day(self) -> None:
        today = datetime.now(self._tz).date()
        if self._current_date == today and self._current_path is not None:
            return
        if self._file is not None:
            try:
                self._file.flush()
                self._file.close()
            except OSError:
                pass
            self._file = None
        self._current_date = today
        self._current_path = self.base_log_dir / f"{self._env_slug}-{today!s}.jsonl"
        try:
            self._current_path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            self._current_path = None

    def _get_file(self) -> Any:
        if self._file is None and self._current_path:
            try:
                self._file = open(self._current_path, "a", encoding="utf-8", buffering=1)
            except OSError:
                return None
        return self._file

    def emit(self, record: logging.LogRecord) -> None:
        with self._lock:
            try:
                self._rotate_if_new_day()
                line = json.dumps(
                    _record_to_log_dict(
                        record,
                        tz=self._tz,
                        message_override=_strip_ansi(record.getMessage()),
                        include_callsite=True,
                    ),
                    default=str,
                    ensure_ascii=False,
                )
                f = self._get_file()
                if f:
                    f.write(line + "\n")
            except Exception:
                self.handleError(record)

    def flush(self) -> None:
        with self._lock:
            if self._file is not None:
                try:
                    self._file.flush()
                except OSError:
                    pass

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                try:
                    self._file.flush()
                    self._file.close()
                except OSError:
                    pass
                self._file = None
        super().close()


class PrettyConsoleFormatter(logging.Formatter):
    """Single-line console format; optional ANSI colors when stdout is a TTY."""

    def __init__(self, service_name: str = "app", use_color: bool | None = None) -> None:
        super().__init__()
        self.service_name = service_name
        self._use_color = use_color if use_color is not None else sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        at = datetime.fromtimestamp(record.created, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        if self._use_color:
            color = _LEVEL_COLORS.get(level, _RESET)
            head = (
                f"{_DIM}{at}{_RESET} {color}{level:5}{_RESET} "
                f"{_DIM}[{record.name}]{_RESET} {record.getMessage()}"
            )
        else:
            head = f"{at} {level:5} [{record.name}] {record.getMessage()}"

        tail: list[str] = _context_kv_strings()
        for k, v in record.__dict__.items():
            if k not in _SKIP_RECORD_KEYS and v is not None:
                tail.append(f"{k}={v}")
        suffix = (" " + " ".join(tail)) if tail else ""

        if record.exc_info:
            exc = self.formatException(record.exc_info)
            if self._use_color:
                suffix += f"\n\033[31m{exc}{_RESET}"
            else:
                suffix += "\n" + exc
        return head + suffix


class JsonFormatter(logging.Formatter):
    """One JSON object per line (compact; omit callsite for smaller aggregator payloads)."""

    def __init__(self, service_name: str = "app") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            _record_to_log_dict(
                record, tz=UTC, service_name=self.service_name, include_callsite=False
            ),
            default=str,
            ensure_ascii=False,
        )


class ContextFilter(logging.Filter):
    """Expose ``request_id`` on the record (legacy); contextvars drive structured output."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()  # type: ignore[attr-defined]
        return True


def _wire_handler(
    handler: logging.Handler,
    level: int,
    *,
    formatter: logging.Formatter,
) -> None:
    handler.setLevel(level)
    handler.addFilter(ContextFilter())
    handler.setFormatter(formatter)


def configure_logging(
    level: str | None = None,
    service_name: str = "app",
    log_file: str = "",
) -> None:
    """Configure the root logger: console + optional JSONL directory or single JSON file."""
    lvl_name = (level or settings.LOG_LEVEL).upper()
    lvl = getattr(logging, lvl_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(lvl)
    for h in root.handlers[:]:
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stdout)
    _wire_handler(
        console,
        lvl,
        formatter=PrettyConsoleFormatter(service_name=service_name),
    )
    root.addHandler(console)

    log_dir = settings.LOG_DIR
    if log_dir and str(log_dir).strip():
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        fh = JsonlFileHandler(Path(log_dir))
        fh.setLevel(lvl)
        fh.addFilter(ContextFilter())
        root.addHandler(fh)
    elif log_file or settings.LOG_FILE:
        path = log_file or settings.LOG_FILE
        fh = logging.FileHandler(path, encoding="utf-8")
        _wire_handler(fh, lvl, formatter=JsonFormatter(service_name=service_name))
        root.addHandler(fh)

    _apply_third_party_log_levels()


def _apply_third_party_log_levels() -> None:
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    for name in _NOISY_LIB_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def align_uvicorn_with_root() -> None:
    """After uvicorn's ``dictConfig``, route uvicorn loggers through root (same console format)."""
    root = logging.getLogger()
    lvl = root.level
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.setLevel(logging.WARNING)
    access.propagate = True
    for name in _UVICORN_PROPAGATE:
        log = logging.getLogger(name)
        log.handlers.clear()
        log.setLevel(lvl)
        log.propagate = True
