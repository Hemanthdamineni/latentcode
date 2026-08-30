"""Aggregate metrics from a server process and probe results."""
from __future__ import annotations

from collections import Counter
from statistics import mean, median


def collect_metrics(proc, endpoints: list[dict], base: dict | None = None) -> dict:
    metrics = dict(base or {})

    statuses = [e.get("status") for e in endpoints if e.get("status") is not None]
    latencies = [e["latency_ms"] for e in endpoints if e.get("latency_ms") is not None]
    errors = [e for e in endpoints if e.get("error")]

    metrics["endpoints_total"] = len(endpoints)
    metrics["endpoints_2xx_3xx"] = sum(1 for s in statuses if 200 <= s < 400)
    metrics["endpoints_4xx_5xx"] = sum(1 for s in statuses if s >= 400)
    metrics["endpoints_unreachable"] = len(errors)
    metrics["latency_avg_ms"] = round(mean(latencies), 2) if latencies else 0
    metrics["latency_p50_ms"] = round(median(latencies), 2) if latencies else 0
    metrics["status_breakdown"] = dict(Counter(statuses))

    if proc.process and proc.process.pid:
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            metrics["peak_memory_mb"] = round(usage.ru_maxrss / 1024, 2)
        except (ImportError, OSError):
            pass

    return metrics