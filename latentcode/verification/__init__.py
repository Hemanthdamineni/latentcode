"""Verification framework — declared, sandboxed actions for E2E testing.

Per audit revision Challenge 2: the runtime prober is no longer HTTP-GET
only. The user authors a `verification_spec.yaml` that declares exactly
which actions to run, and LatentCode executes them in a sandbox with
DB isolation + automatic cleanup.

Three safety properties:
  1. Declared only — LatentCode will not invent endpoints or payloads
  2. Sandboxed by default — DB swap, loopback-only binding
  3. Explicit cleanup — even on failure, the test environment is restored

Public surface:
    load_spec(path) -> VerificationSpec
    run_verification(spec, repo, base_url) -> VerificationResult
"""
from __future__ import annotations

from .spec import load_spec, VerificationSpec, Action, HttpStep, UiStep
from .runner import run_verification, VerificationResult, ActionResult, StepResult
from .isolation import NoOpIsolation, isolation_context, default_isolation

__all__ = [
    "load_spec",
    "VerificationSpec",
    "Action",
    "HttpStep",
    "UiStep",
    "run_verification",
    "VerificationResult",
    "ActionResult",
    "StepResult",
    "NoOpIsolation",
    "isolation_context",
    "default_isolation",
]