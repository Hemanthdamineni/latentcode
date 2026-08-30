"""Verification runner — executes declared actions and records results.

HTTP actions are run with stdlib (urllib). UI actions require playwright
and are stubbed to return `not_implemented` when the dep is missing.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .isolation import isolation_context
from .spec import Action, HttpStep, UiStep, VerificationSpec


@dataclass
class StepResult:
    index: int
    name: str
    method: str
    path: str
    status: int | None = None
    latency_ms: float | None = None
    passed: bool = False
    error: str | None = None
    body_excerpt: str = ""
    saved_as: str | None = None


@dataclass
class ActionResult:
    name: str
    type: str
    passed: bool
    duration_ms: float
    steps: list[StepResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "steps": [asdict(s) for s in self.steps],
        }


@dataclass
class VerificationResult:
    repo: Path
    base_url: str
    actions_total: int
    actions_passed: int
    actions_failed: int
    action_results: list[ActionResult] = field(default_factory=list)
    isolation: dict = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "repo": str(self.repo),
            "base_url": self.base_url,
            "actions_total": self.actions_total,
            "actions_passed": self.actions_passed,
            "actions_failed": self.actions_failed,
            "isolation": self.isolation,
            "duration_ms": self.duration_ms,
            "actions": [a.to_dict() for a in self.action_results],
        }

    def passed_actions(self) -> list[str]:
        return [a.name for a in self.action_results if a.passed]

    def failed_actions(self) -> list[str]:
        return [a.name for a in self.action_results if not a.passed]


def run_verification(
    spec: VerificationSpec,
    base_url: str = "http://127.0.0.1:3000",
    stop_on_failure: bool = True,
) -> VerificationResult:
    """Execute every action in the spec, in declaration order.

    Within an action, steps run sequentially with variable expansion.
    Across actions, the spec's `isolation.parallel` flag determines
    whether we run them concurrently (sequential today; concurrency is
    gated on the same-DB / different-DB story).
    """
    start = time.time()
    with isolation_context(spec.isolation, spec.repo):
        results: list[ActionResult] = []
        for action in spec.actions:
            res = _run_action(action, base_url)
            results.append(res)
            if not res.passed and stop_on_failure:
                # Mark remaining actions as skipped
                for skipped in spec.actions[len(results):]:
                    results.append(ActionResult(
                        name=skipped.name, type=skipped.type, passed=False,
                        duration_ms=0.0, error="skipped: previous action failed",
                    ))
                break

    passed = sum(1 for r in results if r.passed)
    return VerificationResult(
        repo=spec.repo,
        base_url=base_url,
        actions_total=len(spec.actions),
        actions_passed=passed,
        actions_failed=len(results) - passed,
        action_results=results,
        isolation={
            "database": spec.isolation.database,
            "cleanup": spec.isolation.cleanup,
            "env_overrides": spec.isolation.env_overrides,
        },
        duration_ms=round((time.time() - start) * 1000, 2),
    )


def _run_action(action: Action, base_url: str) -> ActionResult:
    start = time.time()
    if action.type == "ui":
        return _run_ui_action(action, base_url, start)
    return _run_http_action(action, base_url, start)


def _run_http_action(action: Action, base_url: str, start: float) -> ActionResult:
    step_results: list[StepResult] = []
    variables: dict[str, Any] = {}
    overall_pass = True
    overall_error: str | None = None

    for i, raw_step in enumerate(action.steps):
        if not isinstance(raw_step, HttpStep):
            continue
        step = StepResult(index=i, name=f"step {i+1}", method=raw_step.method, path=raw_step.path)
        url = base_url.rstrip("/") + raw_step.path
        headers = {k: _expand(v, variables) for k, v in raw_step.headers.items()}
        body_data = None
        if raw_step.body is not None:
            body_data = json.dumps(_expand(raw_step.body, variables)).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        step.name = f"{raw_step.method} {raw_step.path}"
        t = time.time()
        try:
            req = urllib.request.Request(url, data=body_data, method=raw_step.method, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                step.status = resp.getcode()
                body = resp.read(8192)
                step.body_excerpt = body[:512].decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            step.status = exc.code
            try:
                step.body_excerpt = exc.read(512).decode("utf-8", errors="ignore")
            except Exception:
                pass
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            step.error = str(exc)[:200]
            step.passed = False
            overall_pass = False
            overall_error = step.error
            step.latency_ms = round((time.time() - t) * 1000, 2)
            step_results.append(step)
            break
        step.latency_ms = round((time.time() - t) * 1000, 2)

        # Save response for later steps
        if raw_step.save_as:
            try:
                variables[raw_step.save_as] = json.loads(step.body_excerpt) if step.body_excerpt else {}
            except json.JSONDecodeError:
                variables[raw_step.save_as] = {"_raw": step.body_excerpt}
            step.saved_as = raw_step.save_as

        # Verify expectations
        if raw_step.expect_status is not None and step.status != raw_step.expect_status:
            step.passed = False
            step.error = f"expected status {raw_step.expect_status}, got {step.status}"
            overall_pass = False
        elif raw_step.expect_contains:
            try:
                payload = json.loads(step.body_excerpt) if step.body_excerpt else {}
            except json.JSONDecodeError:
                payload = {}
            if not _contains(payload, raw_step.expect_contains):
                step.passed = False
                step.error = f"expected payload to contain {raw_step.expect_contains}, got {payload}"
                overall_pass = False
            else:
                step.passed = True
        else:
            step.passed = step.status is not None and 200 <= step.status < 400

        if not step.passed:
            overall_pass = False
            if not overall_error:
                overall_error = step.error
        step_results.append(step)

    return ActionResult(
        name=action.name, type="http", passed=overall_pass,
        duration_ms=round((time.time() - start) * 1000, 2),
        steps=step_results, error=overall_error,
    )


def _run_ui_action(action: Action, base_url: str, start: float) -> ActionResult:
    """UI actions require playwright. If missing, mark not-implemented.

    Soft dependency: install with `pip install playwright && playwright install`.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return ActionResult(
            name=action.name, type="ui", passed=False,
            duration_ms=round((time.time() - start) * 1000, 2),
            error="playwright not installed; pip install playwright && playwright install",
        )

    step_results: list[StepResult] = []
    overall_pass = True
    overall_error: str | None = None

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            for i, raw_step in enumerate(action.steps):
                if not isinstance(raw_step, UiStep):
                    continue
                step = StepResult(index=i, name=f"ui step {i+1}", method="UI", path="")
                t = time.time()
                try:
                    for op in raw_step.steps:
                        if "click" in op:
                            page.click(op["click"])
                        elif "fill" in op:
                            fill = op["fill"]
                            page.fill(fill["selector"], fill["value"])
                        elif "goto" in op:
                            page.goto(op["goto"])
                        elif "assert_visible" in op:
                            assert page.locator(op["assert_visible"]).is_visible(), f"not visible: {op['assert_visible']}"
                    step.passed = True
                except Exception as exc:
                    step.passed = False
                    step.error = str(exc)[:200]
                    overall_pass = False
                    overall_error = step.error
                step.latency_ms = round((time.time() - t) * 1000, 2)
                step_results.append(step)
        finally:
            browser.close()

    return ActionResult(
        name=action.name, type="ui", passed=overall_pass,
        duration_ms=round((time.time() - start) * 1000, 2),
        steps=step_results, error=overall_error,
    )


def _expand(value: Any, variables: dict[str, Any]) -> Any:
    """Recursively expand ${var} and ${var.path} references in strings."""
    if isinstance(value, str):
        if "${" not in value:
            return value
        import re
        def _sub(m):
            path = m.group(1).split(".")
            cur: Any = variables
            for p in path:
                if isinstance(cur, dict):
                    cur = cur.get(p, m.group(0))
                else:
                    return m.group(0)
            return str(cur)
        return re.sub(r"\$\{([^}]+)\}", _sub, value)
    if isinstance(value, dict):
        return {k: _expand(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v, variables) for v in value]
    return value


def _contains(payload: Any, expected: dict) -> bool:
    """Check that every (key, value) in `expected` is present in `payload`."""
    if not isinstance(payload, dict):
        return False
    for k, v in expected.items():
        if k not in payload:
            return False
        if isinstance(v, dict) and isinstance(payload[k], dict):
            if not _contains(payload[k], v):
                return False
        elif payload[k] != v:
            return False
    return True