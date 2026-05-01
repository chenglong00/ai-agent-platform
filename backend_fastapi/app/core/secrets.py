"""Secret loading hook: cloud-agnostic by default, pluggable for AWS/GCP later.

Secrets are read from the environment (see .env.example). This module is called
from config.prepare_settings() so a future integration can populate os.environ
from a cloud secret manager (e.g. AWS Secrets Manager, GCP Secret Manager)
without changing the rest of the app.
"""

from __future__ import annotations


def prepare_secrets() -> None:
    """Load secrets into the process environment before Settings are created.

    Default: no-op (secrets come from env files / process env).

    To use a cloud secret manager later:
    - Implement a loader that fetches secrets and sets os.environ.
    - This function is invoked from app.core.config.prepare_settings() before
      Settings() is created, so any first importer of config gets the updated
      environment. See docs/SECRETS.md.
    """
    pass
