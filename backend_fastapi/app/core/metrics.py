"""Prometheus metrics: request count and latency exposed at /metrics."""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


def setup_metrics(app: FastAPI) -> None:
    """Register Prometheus instrumentation and /metrics endpoint."""
    Instrumentator().instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
    )
