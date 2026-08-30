"""Discover routes per framework — file-based, no server boot required."""
from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {"node_modules", ".next", "dist", "build", "__pycache__", ".venv", "venv"}


def discover_routes(repo: Path, framework: str) -> list[str]:
    routes: set[str] = set()
    if framework == "nextjs":
        for path in repo.rglob("*"):
            if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.name in ("route.ts", "route.js", "route.mjs"):
                parts = path.parts
                if "api" in parts:
                    idx = parts.index("api")
                    route = "/" + "/".join(parts[idx:-1])
                    if route:
                        routes.add(route)
            if path.name in ("page.tsx", "page.js"):
                parts = path.parts
                for marker in ("app", "pages", "src/app", "src/pages"):
                    if marker in parts:
                        idx = parts.index(marker)
                        sub = "/".join(parts[idx + 1:-1])
                        route = "/" + sub
                        routes.add(route or "/")
    elif framework == "express":
        pat = re.compile(r"""['"`]([/:a-zA-Z0-9_\-]+)['"`]""")
        for path in repo.rglob("*.js"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in pat.finditer(text):
                val = m.group(1)
                if val.startswith("/"):
                    routes.add(val)
    elif framework == "fastapi":
        pat = re.compile(r'@app\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']')
        for path in repo.rglob("*.py"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in pat.finditer(text):
                routes.add(m.group(2))
    return sorted(routes)