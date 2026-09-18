"""Probe each declared route with a HEAD/GET and record status + timing."""
from __future__ import annotations

import time
import urllib.error
import urllib.request


def probe_endpoints(base_url: str, routes: list[str], timeout: float = 5.0) -> list[dict]:
    results: list[dict] = []
    base = base_url.rstrip("/")
    for route in routes:
        if not route.startswith("/"):
            route = "/" + route
        url = base + route
        record = {
            "route": route,
            "url": url,
            "status": None,
            "latency_ms": None,
            "error": None,
            "body_excerpt": "",
        }
        start = time.time()
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                record["status"] = resp.getcode()
                body = resp.read(4096)
                record["body_excerpt"] = body[:512].decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            record["status"] = exc.code
            try:
                record["body_excerpt"] = exc.read(512).decode("utf-8", errors="ignore")
            except Exception:
                pass
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            record["error"] = str(exc)[:200]
        record["latency_ms"] = round((time.time() - start) * 1000, 2)
        results.append(record)
    return results