"""Isolation — sandbox lifecycle for verification runs.

Wraps the project's runtime so verification actions run against an
isolated environment. Today: env-var swap (DATABASE_URL → test DB).
Future: container-based isolation.

The context manager pattern ensures cleanup runs even on failure.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .spec import IsolationConfig


class NoOpIsolation:
    """Default: no isolation, run against whatever env is current."""

    def __init__(self, config: IsolationConfig, repo: Path):
        self.config = config
        self.repo = repo
        self.saved_env: dict[str, str | None] = {}

    def __enter__(self):
        # Apply env_overrides for the duration of the run
        for k, v in self.config.env_overrides.items():
            self.saved_env[k] = os.environ.get(k)
            os.environ[k] = v
        return self

    def __exit__(self, exc_type, exc, tb):
        # Restore
        for k, prev in self.saved_env.items():
            if prev is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = prev


@contextmanager
def isolation_context(config: IsolationConfig, repo: Path) -> Iterator[None]:
    """Yield inside an isolated environment. Currently a thin wrapper around NoOpIsolation.

    Future: switch based on config.database:
      - "use_test_db" → spin up a SQLite/Postgres test DB, set DATABASE_URL
      - "ephemeral_container" → launch the dev server in a container
    """
    with NoOpIsolation(config, repo) as _:
        yield


def default_isolation() -> IsolationConfig:
    """A no-op isolation config for projects that don't need sandboxing."""
    return IsolationConfig()