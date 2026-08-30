"""Verification spec — load + validate `verification_spec.yaml`.

Example:

    isolation:
      database: use_test_db
      cleanup: drop_and_recreate
      parallel: false

    actions:
      - name: "Create a todo and verify"
        steps:
          - method: POST
            path: /api/todos
            body: { title: "test" }
            expect_status: 201
          - method: GET
            path: /api/todos
            expect:
              contains: { title: "test" }
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class HttpStep:
    method: str
    path: str
    body: dict | None = None
    headers: dict[str, str] = field(default_factory=dict)
    expect_status: int | None = None
    expect_contains: dict[str, Any] | None = None
    save_as: str | None = None


@dataclass
class UiStep:
    type: str  # always "ui" for now
    steps: list[dict] = field(default_factory=list)


@dataclass
class Action:
    name: str
    type: str  # "http" | "ui"
    steps: list[Any]  # list[HttpStep] | list[UiStep]


@dataclass
class IsolationConfig:
    database: str = "none"  # "none" | "use_test_db"
    cleanup: str = "drop_and_recreate"  # "drop_and_recreate" | "keep"
    parallel: bool = False
    env_overrides: dict[str, str] = field(default_factory=dict)


@dataclass
class VerificationSpec:
    repo: Path
    isolation: IsolationConfig
    actions: list[Action]

    def by_name(self, name: str) -> Action | None:
        for a in self.actions:
            if a.name == name:
                return a
        return None


def load_spec(path: str | Path) -> VerificationSpec:
    """Load and validate a verification_spec.yaml."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"verification_spec not found at {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"verification_spec at {p} must be a YAML mapping, got {type(raw).__name__}")

    # Default isolation
    isolation_raw = raw.get("isolation", {})
    isolation = IsolationConfig(
        database=isolation_raw.get("database", "none"),
        cleanup=isolation_raw.get("cleanup", "drop_and_recreate"),
        parallel=bool(isolation_raw.get("parallel", False)),
        env_overrides=dict(isolation_raw.get("env_overrides", {})),
    )

    actions_raw = raw.get("actions", [])
    if not isinstance(actions_raw, list) or not actions_raw:
        raise ValueError("verification_spec must contain a non-empty 'actions' list")

    actions: list[Action] = []
    for i, a in enumerate(actions_raw):
        if not isinstance(a, dict):
            raise ValueError(f"action #{i} must be a mapping")
        name = a.get("name")
        if not name:
            raise ValueError(f"action #{i} missing 'name'")
        atype = a.get("type", "http")
        steps_raw = a.get("steps", [])
        if not steps_raw:
            raise ValueError(f"action '{name}' has no steps")

        if atype == "http":
            steps = [_parse_http_step(s) for s in steps_raw]
        elif atype == "ui":
            steps = [UiStep(type="ui", steps=list(s.get("steps", [])) if isinstance(s, dict) else []) for s in steps_raw]
        else:
            raise ValueError(f"action '{name}' has unknown type '{atype}'; expected 'http' or 'ui'")

        actions.append(Action(name=name, type=atype, steps=steps))

    # Validate: step.save_as references exist before they're consumed
    defined_vars: set[str] = set()
    for action in actions:
        for step in action.steps:
            if isinstance(step, HttpStep) and step.save_as:
                defined_vars.add(step.save_as)

    for action in actions:
        for step in action.steps:
            if isinstance(step, HttpStep) and step.headers:
                for k, v in step.headers.items():
                    if isinstance(v, str) and "${" in v:
                        _validate_var_ref(v, defined_vars, action.name)

    return VerificationSpec(repo=p.parent, isolation=isolation, actions=actions)


def _parse_http_step(raw: dict) -> HttpStep:
    if not isinstance(raw, dict):
        raise ValueError(f"HTTP step must be a mapping, got {type(raw).__name__}")
    method = raw.get("method", "GET").upper()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        raise ValueError(f"unsupported HTTP method: {method}")
    path = raw.get("path")
    if not path:
        raise ValueError(f"HTTP step missing 'path'")
    expect = raw.get("expect", {})
    return HttpStep(
        method=method,
        path=path,
        body=raw.get("body"),
        headers=dict(raw.get("headers", {})),
        expect_status=raw.get("expect_status"),
        expect_contains=expect.get("contains") if isinstance(expect, dict) else None,
        save_as=raw.get("save_as"),
    )


def _validate_var_ref(value: str, defined_vars: set[str], action_name: str) -> None:
    """Check that ${var} references are to variables defined earlier in the action."""
    import re
    for m in re.finditer(r"\$\{([^}]+)\}", value):
        # Path can be like "token.token" — take the root
        root = m.group(1).split(".")[0]
        if root not in defined_vars:
            raise ValueError(
                f"action '{action_name}' references ${{{m.group(1)}}} but no earlier step defines save_as='{root}'"
            )