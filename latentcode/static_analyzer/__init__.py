"""Static analysis — extract a graph of files, symbols, imports, calls, routes.

Tooling-first: we use deterministic parsing (regex + tree-sitter when available)
to build the *candidate set*. The LLM judges the semantic meaning.

Public surface:
    run_static_analysis(repo, spec) -> dict
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .dead_export_scan import find_dead_exports
from .issue_graph import build_issue_graph, compute_repair_scope
from .js_analyzer import analyze_js_ts
from .python_analyzer import analyze_python
from .route_discovery import discover_routes

if TYPE_CHECKING:
    from ..project_detect import ProjectSpec


def run_static_analysis(repo: Path, spec: "ProjectSpec", max_scope_depth: int = 3) -> dict:
    repo = Path(repo)
    symbols: list[dict] = []
    imports: list[dict] = []
    calls: list[dict] = []
    stubs: list[dict] = []

    if spec.language in ("javascript", "typescript"):
        symbols, imports, calls, stubs = analyze_js_ts(repo)
    elif spec.language == "python":
        symbols, imports, calls, stubs = analyze_python(repo)

    routes = discover_routes(repo, spec.framework)

    graph = build_issue_graph(repo, symbols, imports, calls, routes)
    dead = find_dead_exports(symbols, imports)

    def _scope_for(file: str, line: int) -> dict:
        return compute_repair_scope(graph, file, line, max_depth=max_scope_depth)

    issues = []
    for d in dead:
        scope = _scope_for(d["file"], 1)
        issues.append({
            "category": "hidden_implementation",
            "subtype": "dead_export",
            "file": d["file"],
            "symbol": d["name"],
            "kind": d["kind"],
            "severity": 0.7 if d["kind"] in ("function", "class", "component") else 0.4,
            "evidence": f"exported `{d['name']}` has no importer in the project",
            "repair_scope": scope,
        })
    for s in stubs:
        scope = _scope_for(s["file"], s.get("line", 1) or 1)
        issues.append({
            "category": "agent_shortcut",
            "subtype": s["subtype"],
            "file": s["file"],
            "line": s["line"],
            "severity": 0.8 if s["subtype"] == "not_implemented" else 0.5,
            "evidence": s["evidence"],
            "snippet": s.get("snippet", ""),
            "repair_scope": scope,
        })
    for missing in _missing_env_vars(spec.env_vars_referenced, repo):
        # Env-var issues have no specific file; the scope is just the referencing files
        scope_files = sorted(missing["files"])
        issues.append({
            "category": "broken_integration",
            "subtype": "env_var_missing",
            "var": missing["name"],
            "files": missing["files"],
            "severity": 0.6,
            "evidence": f"`{missing['name']}` referenced in {len(missing['files'])} file(s) but not in any .env / .env.example",
            "repair_scope": {
                "files": scope_files,
                "depth": 0,
                "rationale": f"env var referenced in {len(scope_files)} files; scope is the referencing files",
            },
        })

    return {
        "language": spec.language,
        "framework": spec.framework,
        "stats": {
            "files_analyzed": len({s["file"] for s in symbols}) or 1,
            "symbols": len(symbols),
            "imports": len(imports),
            "calls": len(calls),
            "routes": len(routes),
            "stubs": len(stubs),
        },
        "graph": graph,
        "issues": issues,
        "routes": routes,
        "symbols": symbols,
        "scope_depth": max_scope_depth,
    }


def _missing_env_vars(referenced: list[str], repo: Path) -> list[dict]:
    """Find env vars referenced in code but not declared in .env / .env.example."""
    declared: set[str] = set()
    for env_file in (".env", ".env.example", ".env.local", ".env.sample"):
        p = repo / env_file
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        declared.add(line.split("=", 1)[0].strip())
            except OSError:
                continue
    # Also harvest from repo root
    missing = []
    for var in referenced:
        if var in declared:
            continue
        # Find files that reference this var
        files: list[str] = []
        skip_dirs = {"node_modules", ".next", "dist", "build", "__pycache__", ".venv", "venv"}
        for path in repo.rglob("*"):
            if not path.is_file() or any(part in skip_dirs for part in path.parts):
                continue
            if path.suffix not in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".py"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if f"process.env.{var}" in text or f"os.environ" in text and var in text:
                files.append(str(path.relative_to(repo)))
                if len(files) >= 5:
                    break
        if files:
            missing.append({"name": var, "files": files})
    return missing