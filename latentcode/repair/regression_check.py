"""Regression check — sectioned before/after report.

Per audit revision Challenge 3: drop the generic `improvement_pct`
composite. The headline output is now four sections:
  1. Feature verification (pass/fail per declared action, with delta)
  2. Integration health (chains working before vs after)
  3. Latency (p50/p95/p99)
  4. Static health (dead exports, latent issues, breakdown by category)

The composite percentage is gone. If a user wants a single number, they
get `feature_verification.delta_actions` (a count of newly-passing
actions), not a percentage of issues.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..project_detect import ProjectSpec


def run_regression_check(
    repo: Path,
    spec: "ProjectSpec",
    pre_findings: dict,
    pre_verification: dict | None = None,
    post_verification: dict | None = None,
) -> dict:
    """Compare the current state against a baseline.

    Args:
        repo: the repo to re-scan
        spec: detected project spec
        pre_findings: baseline findings.json (dict, may be normalized)
        pre_verification: baseline verification_results.json (dict, optional)
        post_verification: current verification_results.json (dict, optional)
            — if not provided, regress won't compute action-level deltas

    Returns: a sectioned report dict (see module docstring).
    """
    from ..static_analyzer import run_static_analysis
    repo = Path(repo)

    # Re-run static analysis on the current state
    post = run_static_analysis(repo, spec)
    pre_issues = pre_findings.get("issues", []) if isinstance(pre_findings, dict) else []
    post_issues = post.get("issues", [])

    pre_keys = {_issue_key(i) for i in pre_issues}
    post_keys = {_issue_key(i) for i in post_issues}
    fixed_issues = sorted(pre_keys - post_keys)
    new_issues = sorted(post_keys - pre_keys)

    report = {
        "feature_verification": _verification_section(pre_verification, post_verification),
        "integration_health": _integration_section(pre_findings, post),
        "latency": _latency_section(pre_findings, post),
        "static_health": {
            "dead_exports": {
                "before": _count_by_subtype(pre_issues, "dead_export"),
                "after": _count_by_subtype(post_issues, "dead_export"),
            },
            "latent_issues": {
                "before": len(pre_issues),
                "after": len(post_issues),
                "fixed": fixed_issues,
                "new": new_issues,
                "by_category": {
                    "before": dict(Counter(i.get("category", "?") for i in pre_issues)),
                    "after": dict(Counter(i.get("category", "?") for i in post_issues)),
                },
            },
        },
    }
    return report


def render_markdown(report: dict) -> str:
    """Render the report as a human-readable Markdown table.

    This is the primary output the user sees — not the JSON.
    """
    lines = ["# LatentCode Regression Report", ""]

    # 1. Feature verification
    fv = report.get("feature_verification", {})
    lines.append("## Feature verification")
    lines.append("")
    if fv.get("actions_total"):
        before = fv.get("passed_before", 0)
        after = fv.get("passed_after", 0)
        total = fv.get("actions_total", 0)
        delta = fv.get("delta_actions", after - before)
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Actions run | {total} |")
        lines.append(f"| Passed BEFORE repair | {before} / {total} |")
        lines.append(f"| Passed AFTER repair | {after} / {total} |")
        lines.append(f"| Newly passing | {delta_str} |")
        lines.append("")
        if fv.get("actions"):
            lines.append("| Action | Before | After |")
            lines.append("|---|---|---|")
            for a in fv["actions"]:
                before_mark = "✓" if a.get("before") == "pass" else "✗"
                after_mark = "✓" if a.get("after") == "pass" else "✗"
                lines.append(f"| {a['name']} | {before_mark} | {after_mark} |")
            lines.append("")
    else:
        lines.append("_No verification results in baseline or current run._")
        lines.append("")

    # 2. Integration health
    ih = report.get("integration_health", {})
    lines.append("## Integration health")
    lines.append("")
    if ih.get("chains_declared") is not None:
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Integration chains declared | {ih.get('chains_declared', 0)} |")
        lines.append(f"| Chains working BEFORE | {ih.get('chains_working_before', 0)} |")
        lines.append(f"| Chains working AFTER | {ih.get('chains_working_after', 0)} |")
        lines.append("")
    else:
        lines.append("_No integration chains declared._")
        lines.append("")

    # 3. Latency
    lat = report.get("latency", {})
    lines.append("## Latency")
    lines.append("")
    if any(lat.values()):
        lines.append("| Percentile | Before | After |")
        lines.append("|---|---|---|")
        for p in ("p50_ms", "p95_ms", "p99_ms"):
            entry = lat.get(p, {})
            if entry:
                lines.append(f"| {p} | {entry.get('before', '?')} ms | {entry.get('after', '?')} ms |")
        lines.append("")
    else:
        lines.append("_No latency data._")
        lines.append("")

    # 4. Static health
    sh = report.get("static_health", {})
    lines.append("## Static health")
    lines.append("")
    lines.append("| Metric | Before | After |")
    lines.append("|---|---|---|")
    de = sh.get("dead_exports", {})
    lines.append(f"| Dead exports | {de.get('before', '?')} | {de.get('after', '?')} |")
    li = sh.get("latent_issues", {})
    lines.append(f"| Latent issues (total) | {li.get('before', '?')} | {li.get('after', '?')} |")
    lines.append(f"| Issues fixed | {len(li.get('fixed', []))} | |")
    lines.append(f"| Issues introduced | {len(li.get('new', []))} | |")
    lines.append("")

    by_cat = li.get("by_category", {})
    if by_cat:
        lines.append("### Issues by category")
        lines.append("")
        lines.append("| Category | Before | After |")
        lines.append("|---|---|---|")
        all_cats = sorted(set(list(by_cat.get("before", {}).keys()) + list(by_cat.get("after", {}).keys())))
        for c in all_cats:
            lines.append(f"| {c} | {by_cat.get('before', {}).get(c, 0)} | {by_cat.get('after', {}).get(c, 0)} |")
        lines.append("")

    return "\n".join(lines)


def _verification_section(pre: dict | None, post: dict | None) -> dict:
    """Compare per-action pass/fail between two verification runs."""
    if not pre and not post:
        return {}

    pre_actions = {a["name"]: a.get("passed", False) for a in (pre or {}).get("actions", [])}
    post_actions = {a["name"]: a.get("passed", False) for a in (post or {}).get("actions", [])}
    all_names = sorted(set(pre_actions) | set(post_actions))

    rows = []
    for name in all_names:
        before = pre_actions.get(name)
        after = post_actions.get(name)
        rows.append({
            "name": name,
            "before": "pass" if before else ("fail" if before is False else "—"),
            "after": "pass" if after else ("fail" if after is False else "—"),
        })

    passed_before = sum(1 for v in pre_actions.values() if v)
    passed_after = sum(1 for v in post_actions.values() if v)

    return {
        "actions_total": len(all_names),
        "passed_before": passed_before,
        "passed_after": passed_after,
        "delta_actions": passed_after - passed_before,
        "actions": rows,
    }


def _integration_section(pre: dict, post: dict) -> dict:
    """Integration chains working before vs after.

    Heuristic: each declared integration that responds 2xx in the
    runtime probe is "working". The runtime probe lives in
    pre.phases.runtime.endpoints (status 200-399) and post.phases.runtime.endpoints.
    """
    pre_endpoints = (pre.get("phases", {}) or {}).get("runtime", {}).get("endpoints", [])
    post_endpoints = (post.get("phases", {}) or {}).get("runtime", {}).get("endpoints", [])
    if not pre_endpoints and not post_endpoints:
        return {}

    def _working(eps):
        return sum(1 for e in eps if isinstance(e.get("status"), int) and 200 <= e["status"] < 400)

    return {
        "chains_declared": max(len(pre_endpoints), len(post_endpoints)),
        "chains_working_before": _working(pre_endpoints),
        "chains_working_after": _working(post_endpoints),
    }


def _latency_section(pre: dict, post: dict) -> dict:
    """Compare latency percentiles."""
    def _p(eps, p):
        lats = sorted(e.get("latency_ms") for e in eps if e.get("latency_ms") is not None)
        if not lats:
            return None
        idx = max(0, min(len(lats) - 1, int(len(lats) * p) - 1))
        return round(lats[idx], 1)

    pre_eps = (pre.get("phases", {}) or {}).get("runtime", {}).get("endpoints", [])
    post_eps = (post.get("phases", {}) or {}).get("runtime", {}).get("endpoints", [])
    if not pre_eps and not post_eps:
        return {}

    return {
        "p50_ms": {"before": _p(pre_eps, 0.5), "after": _p(post_eps, 0.5)},
        "p95_ms": {"before": _p(pre_eps, 0.95), "after": _p(post_eps, 0.95)},
        "p99_ms": {"before": _p(pre_eps, 0.99), "after": _p(post_eps, 0.99)},
    }


def _count_by_subtype(issues: list[dict], subtype: str) -> int:
    return sum(1 for i in issues if i.get("subtype") == subtype)


def _issue_key(issue: dict) -> str:
    """Stable identity for an issue."""
    file = issue.get("file") or issue.get("var") or "?"
    raw_line = issue.get("line")
    line = 0 if raw_line in (None, 0) else raw_line
    subtype = issue.get("subtype", "?")
    return f"{file}::{line}::{subtype}"