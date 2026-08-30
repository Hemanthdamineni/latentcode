"""Python analyzer — symbols, imports, calls, stubs."""
from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules", "dist", "build"}
FUNCTIONS = re.compile(r"^(\s*)def\s+([A-Za-z_][\w]*)\s*\(", re.MULTILINE)
CLASSES = re.compile(r"^(\s*)class\s+([A-Za-z_][\w]*)", re.MULTILINE)
IMPORTS = [
    re.compile(r"^from\s+([\w.]+)\s+import\s+([\w, *]+)", re.MULTILINE),
    re.compile(r"^import\s+([\w.]+)", re.MULTILINE),
]
CALL_PATTERN = re.compile(r"\b([A-Za-z_][\w]*)\s*\(")
STUB_PATTERNS = [
    (re.compile(r"#\s*TODO"), "todo_comment"),
    (re.compile(r"#\s*FIXME"), "fixme_comment"),
    (re.compile(r"raise\s+NotImplementedError"), "not_implemented"),
    (re.compile(r"pass\s*$"), "pass_in_handler"),
]


def _iter_source_files(repo: Path):
    for path in repo.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def analyze_python(repo: Path) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    symbols: list[dict] = []
    imports: list[dict] = []
    calls: list[dict] = []
    stubs: list[dict] = []

    for path in _iter_source_files(repo):
        rel = str(path.relative_to(repo))
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()

        for m in FUNCTIONS.finditer(text):
            line = text[:m.start()].count("\n") + 1
            name = m.group(2)
            symbols.append({
                "file": rel,
                "name": name,
                "kind": "function",
                "exported": not name.startswith("_"),
                "line": line,
            })

        for m in CLASSES.finditer(text):
            line = text[:m.start()].count("\n") + 1
            name = m.group(2)
            symbols.append({
                "file": rel,
                "name": name,
                "kind": "class",
                "exported": not name.startswith("_"),
                "line": line,
            })

        for pat in IMPORTS:
            for m in pat.finditer(text):
                line = text[:m.start()].count("\n") + 1
                source = m.group(1)
                names_raw = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
                names = [n.strip() for n in names_raw.split(",") if n.strip()] if names_raw else [source.split(".")[0]]
                for name in names:
                    imports.append({
                        "from_file": rel,
                        "name": name,
                        "source": source,
                        "line": line,
                    })

        for pat, subtype in STUB_PATTERNS:
            for m in pat.finditer(text):
                line = text[:m.start()].count("\n") + 1
                snippet = "\n".join(lines[max(0, line - 2):line + 2])
                stubs.append({
                    "file": rel,
                    "line": line,
                    "subtype": subtype,
                    "evidence": f"{subtype} at {rel}:{line}",
                    "snippet": snippet[:500],
                })

    # Dedupe
    seen = set()
    unique_symbols = []
    for s in symbols:
        key = (s["file"], s["name"])
        if key in seen:
            continue
        seen.add(key)
        unique_symbols.append(s)

    return unique_symbols, imports, calls, stubs