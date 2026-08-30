"""Aggregate pipeline output into JSON + Markdown findings."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def write_findings(payload: dict, out_dir: Path) -> dict:
    """Write findings.json and findings.md. Return the normalized dict.

    payload: the combined static + runtime + project spec output.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    findings = _normalize(payload)
    findings["generated_at"] = datetime.now(timezone.utc).isoformat()

    (out_dir / "findings.json").write_text(
        json.dumps(findings, indent=2),
        encoding="utf-8",
    )
    (out_dir / "findings.md").write_text(_render_markdown(findings), encoding="utf-8")
    return findings


def _normalize(payload: dict) -> dict:
    """Normalize the raw pipeline output into a stable shape."""
    project = payload.get("project", {})
    phases = payload.get("phases", {})
    static = phases.get("static", {})
    runtime = phases.get("runtime", {})

    issues = static.get("issues", [])
    # Categorize
    by_category = Counter(i["category"] for i in issues)
    by_severity = sorted(issues, key=lambda i: i.get("severity", 0), reverse=True)

    return {
        "project": project,
        "static": {
            "stats": static.get("stats", {}),
            "graph": static.get("graph", {}),
            "routes": static.get("routes", []),
        },
        "runtime": {
            "endpoints": runtime.get("endpoints", []),
            "metrics": runtime.get("metrics", {}),
            "routes_working": runtime.get("routes_working", 0),
            "routes_failing": runtime.get("routes_failing", 0),
        },
        "issues": issues,
        "summary": {
            "total_issues": len(issues),
            "by_category": dict(by_category),
            "top_severity": [
                {"file": i.get("file"), "category": i.get("category"),
                 "severity": i.get("severity"), "evidence": i.get("evidence")}
                for i in by_severity[:10]
            ],
        },
    }


def _render_markdown(findings: dict) -> str:
    lines = ["# LatentCode Findings", ""]
    project = findings.get("project", {})
    lines.append("## Project")
    lines.append("")
    lines.append(f"- **Language**: {project.get('language', 'unknown')}")
    lines.append(f"- **Framework**: {project.get('framework', 'unknown')}")
    lines.append(f"- **Package manager**: {project.get('package_manager', 'unknown')}")
    if project.get("entry_points"):
        lines.append(f"- **Entry points**: {', '.join(project['entry_points'][:5])}")
    if project.get("declared_features"):
        lines.append("")
        lines.append("### Declared features")
        for f in project["declared_features"][:10]:
            lines.append(f"- {f}")
    lines.append("")

    summary = findings.get("summary", {})
    lines.append("## Summary")
    lines.append("")
    lines.append(f"**Total issues**: {summary.get('total_issues', 0)}")
    lines.append("")
    lines.append("By category:")
    for cat, count in (summary.get("by_category") or {}).items():
        lines.append(f"- `{cat}`: {count}")
    lines.append("")

    static = findings.get("static", {})
    stats = static.get("stats", {})
    if stats:
        lines.append("## Static analysis")
        lines.append("")
        for k, v in stats.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    runtime = findings.get("runtime", {})
    if runtime and not runtime.get("skipped"):
        lines.append("## Runtime probe")
        lines.append("")
        lines.append(f"- **Endpoints working**: {runtime.get('routes_working', 0)}")
        lines.append(f"- **Endpoints failing**: {runtime.get('routes_failing', 0)}")
        metrics = runtime.get("metrics", {})
        if metrics:
            lines.append(f"- **Cold start**: {metrics.get('cold_start_seconds', '?')}s")
            if metrics.get("latency_avg_ms"):
                lines.append(f"- **Avg latency**: {metrics['latency_avg_ms']}ms")
        lines.append("")

    issues = findings.get("issues", [])
    if issues:
        lines.append("## Issues")
        lines.append("")
        by_sev = sorted(issues, key=lambda i: i.get("severity", 0), reverse=True)
        for i in by_sev[:50]:
            sev = i.get("severity", 0)
            lines.append(f"### {i.get('category', '?')} — severity {sev:.2f}")
            lines.append(f"- **Location**: `{i.get('file', '?')}:{i.get('line', '?')}`")
            lines.append(f"- **Subtype**: `{i.get('subtype', '?')}`")
            lines.append(f"- **Evidence**: {i.get('evidence', '')}")
            if i.get("snippet"):
                lines.append("")
                lines.append("```")
                lines.append(i["snippet"])
                lines.append("```")
            lines.append("")

    return "\n".join(lines)