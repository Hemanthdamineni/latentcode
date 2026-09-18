"""Find exported symbols that have no importers in the project."""
from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath


# Frameworks that use file-based routing treat whole files as entry points.
# Any symbol exported from a route file is reachable by virtue of the file path.
_ROUTE_FILE_PATTERNS = (
    "/pages/api/", "/pages/", "/app/api/", "/app/",
    "/api/", "/routes/", "/endpoints/",
)


def find_dead_exports(symbols: list[dict], imports: list[dict]) -> list[dict]:
    """Return list of {file, name, kind} for exported symbols that are never imported."""
    imported_names: dict[str, int] = defaultdict(int)
    for i in imports:
        imported_names[i["name"]] += 1

    dead = []
    seen = set()
    for s in symbols:
        if not s.get("exported"):
            continue
        if s["kind"] not in ("function", "class", "component", "component_or_arrow", "const"):
            continue
        key = (s["file"], s["name"])
        if key in seen:
            continue
        seen.add(key)
        # Allow entry-point files to be unused themselves
        if s["file"] in ("index.js", "main.ts", "app.tsx", "main.py", "__init__.py"):
            continue
        # Route handlers are reachable via the route registry, not via imports
        if any(pat in ("/" + s["file"]) for pat in _ROUTE_FILE_PATTERNS):
            continue
        if imported_names.get(s["name"], 0) == 0:
            dead.append({"file": s["file"], "name": s["name"], "kind": s["kind"]})
    return dead