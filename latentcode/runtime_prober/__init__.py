"""Runtime probe — actually start the project and see what works.

Layers:
    1. server_lifecycle: spawn dev/start command, capture logs, wait for ready
    2. endpoint_probe:   curl each declared route, record status/latency/body
    3. metrics_collector: aggregate timings, cold start, peak memory
    4. e2e_runner:       optional headless probe for UI features (Playwright)
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .server_lifecycle import ServerProcess
from .endpoint_probe import probe_endpoints
from .metrics_collector import collect_metrics

if TYPE_CHECKING:
    from ..project_detect import ProjectSpec


def run_runtime_probe(repo: Path, spec: "ProjectSpec", allow_remote: bool = False) -> dict:
    """Boot the project (if dev_cmd available), probe endpoints, collect metrics.

    Safe to run when no dev_cmd exists — returns empty result.

    allow_remote: by default the server is forced to bind to loopback only.
    Set True to allow non-loopback binding (e.g. for testing on a remote box).
    """
    repo = Path(repo)

    if not spec.dev_cmd:
        return {
            "skipped": True,
            "reason": "no dev_cmd detected",
            "endpoints": [],
            "metrics": {},
        }

    metrics: dict = {}
    endpoints: list[dict] = []
    server_logs = ""

    try:
        with ServerProcess(repo, spec.dev_cmd, spec.package_manager, allow_remote=allow_remote) as proc:
            if proc.safety_error:
                return {
                    "skipped": True,
                    "reason": proc.safety_error,
                    "endpoints": [],
                    "metrics": {},
                }
            metrics["cold_start_seconds"] = proc.startup_seconds
            server_logs = proc.logs_so_far()
            endpoints = probe_endpoints(proc.base_url, spec.routes)
            metrics = collect_metrics(proc, endpoints, metrics)
            metrics["server_logs_excerpt"] = server_logs[-2000:]
    except Exception as exc:
        return {
            "error": str(exc),
            "endpoints": endpoints,
            "metrics": metrics,
        }

    return {
        "endpoints": endpoints,
        "metrics": metrics,
        "routes_declared": len(spec.routes),
        "routes_working": sum(1 for e in endpoints if 200 <= e.get("status", 0) < 400),
        "routes_failing": sum(1 for e in endpoints if e.get("status", 0) >= 400 or e.get("error")),
    }