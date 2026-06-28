"""Shared security primitives (crypto, passwords, OAuth client, DB session)."""

from app.core.security.dependencies import get_db

__all__ = ["get_db"]
