"""Detect project type, framework, entry points, and build/dev commands.

Output: ProjectSpec used by every downstream analyzer.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class ProjectSpec:
    repo_root: str
    language: str               # "javascript" | "typescript" | "python" | "go" | "unknown"
    framework: str              # "nextjs" | "fastapi" | "express" | "django" | "flask" | "unknown"
    package_manager: str        # "npm" | "pnpm" | "yarn" | "uv" | "pip" | "go"
    entry_points: list[str] = field(default_factory=list)
    build_cmd: Optional[str] = None
    dev_cmd: Optional[str] = None
    test_cmd: Optional[str] = None
    declared_features: list[str] = field(default_factory=list)
    declared_integrations: list[str] = field(default_factory=list)
    env_vars_referenced: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _detect_node(repo: Path) -> Optional[ProjectSpec]:
    pkg_path = repo / "package.json"
    pkg = _read_json(pkg_path)
    if not pkg:
        return None
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    scripts = pkg.get("scripts", {})

    framework = "unknown"
    if "next" in deps:
        framework = "nextjs"
    elif "express" in deps:
        framework = "express"
    elif "fastify" in deps:
        framework = "fastify"

    language = "typescript" if "typescript" in deps or (repo / "tsconfig.json").exists() else "javascript"

    pkg_manager = "npm"
    if (repo / "pnpm-lock.yaml").exists():
        pkg_manager = "pnpm"
    elif (repo / "yarn.lock").exists():
        pkg_manager = "yarn"

    entry_points = []
    if framework == "nextjs":
        pages_dir = repo / "pages"
        app_dir = repo / "app"
        src_app_dir = repo / "src" / "app"
        for base in [pages_dir, app_dir, src_app_dir]:
            if base.exists():
                for p in base.rglob("*.tsx"):
                    if p.name in ("page.tsx", "index.tsx"):
                        entry_points.append(str(p.relative_to(repo)))
                    elif p.name == "route.ts":
                        entry_points.append(str(p.relative_to(repo)))
                for p in base.rglob("*.ts"):
                    if p.name == "route.ts":
                        entry_points.append(str(p.relative_to(repo)))
                for p in base.rglob("*.js"):
                    if p.name in ("page.js", "index.js", "route.js"):
                        entry_points.append(str(p.relative_to(repo)))
    else:
        main_field = pkg.get("main") or "index.js"
        if (repo / main_field).exists():
            entry_points.append(main_field)

    spec = ProjectSpec(
        repo_root=str(repo),
        language=language,
        framework=framework,
        package_manager=pkg_manager,
        entry_points=entry_points,
        build_cmd=scripts.get("build"),
        dev_cmd=scripts.get("dev") or scripts.get("start"),
        test_cmd=scripts.get("test"),
    )

    declared = _extract_declared_features(pkg, repo)
    spec.declared_features = declared
    spec.declared_integrations = _extract_integrations(deps)
    spec.env_vars_referenced = _scan_env_vars(repo)
    spec.routes = _scan_routes(repo, framework)
    return spec


def _detect_python(repo: Path) -> Optional[ProjectSpec]:
    pyproject = repo / "pyproject.toml"
    requirements = repo / "requirements.txt"
    setup_py = repo / "setup.py"
    if not (pyproject.exists() or requirements.exists() or setup_py.exists()):
        return None

    deps_text = ""
    if pyproject.exists():
        deps_text += pyproject.read_text(encoding="utf-8", errors="ignore")
    if requirements.exists():
        deps_text += "\n" + requirements.read_text(encoding="utf-8", errors="ignore")

    framework = "unknown"
    if "fastapi" in deps_text.lower():
        framework = "fastapi"
    elif "django" in deps_text.lower():
        framework = "django"
    elif "flask" in deps_text.lower():
        framework = "flask"

    entry_points = []
    for candidate in ["main.py", "app.py", "server.py", "wsgi.py", "asgi.py"]:
        if (repo / candidate).exists():
            entry_points.append(candidate)

    pkg_manager = "uv" if (repo / "uv.lock").exists() else "pip"

    spec = ProjectSpec(
        repo_root=str(repo),
        language="python",
        framework=framework,
        package_manager=pkg_manager,
        entry_points=entry_points,
        build_cmd=None,
        dev_cmd=None,
        test_cmd="pytest",
    )
    spec.declared_features = _extract_declared_features(None, repo)
    spec.declared_integrations = _extract_integrations({"__raw__": deps_text})
    spec.env_vars_referenced = _scan_env_vars(repo)
    spec.routes = _scan_routes(repo, framework)
    return spec


def _detect_go(repo: Path) -> Optional[ProjectSpec]:
    go_mod = repo / "go.mod"
    if not go_mod.exists():
        return None
    return ProjectSpec(
        repo_root=str(repo),
        language="go",
        framework="unknown",
        package_manager="go",
        entry_points=[],
        build_cmd="go build ./...",
        dev_cmd="go run ./...",
        test_cmd="go test ./...",
    )


def _extract_declared_features(pkg: Optional[dict], repo: Path) -> list[str]:
    """Heuristic: read README first 200 lines for feature bullets / sections."""
    candidates = [repo / "README.md", repo / "readme.md", repo / "README.rst"]
    features = []
    for c in candidates:
        if not c.exists():
            continue
        text = c.read_text(encoding="utf-8", errors="ignore")[:10000]
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- ", "* ", "## ", "### ")):
                content = re.sub(r"^[-*#\s]+", "", stripped)
                content = content.split("—")[0].split("–")[0].split(":")[0].strip()
                if 3 < len(content) < 80:
                    features.append(content)
        break
    return features[:50]


def _extract_integrations(deps: dict | dict[str, str]) -> list[str]:
    """Heuristic: look for known integration SDK names in deps."""
    known = {
        "stripe", "aws-sdk", "@aws-sdk", "@supabase/supabase-js",
        "firebase", "@google-cloud", "openai", "@anthropic-ai/sdk",
        "@slack/web-api", "twilio", "sendgrid", "mongodb", "mongoose",
        "prisma", "@prisma/client", "drizzle-orm", "pg", "mysql2",
        "redis", "ioredis", "bullmq", "next-auth", "auth0", "clerk",
        "passport", "jsonwebtoken", "axios", "graphql", "@apollo/client",
    }
    found = []
    keys = list(deps.keys()) if isinstance(deps, dict) else []
    raw = deps.get("__raw__", "") if "__raw__" in deps else ""
    for k in keys:
        kl = k.lower()
        for known_name in known:
            if known_name in kl:
                found.append(known_name)
    if raw:
        rl = raw.lower()
        for known_name in known:
            if known_name in rl and known_name not in found:
                found.append(known_name)
    return sorted(set(found))


def _scan_env_vars(repo: Path) -> list[str]:
    """Scan source for `process.env.X` or `os.environ["X"]` references."""
    pattern_js = re.compile(r"process\.env\.([A-Z_][A-Z0-9_]*)")
    pattern_py = re.compile(r"os\.environ(?:\[['\"]|get\(\s*['\"])([A-Z_][A-Z0-9_]*)")
    found: set[str] = set()
    skip_dirs = {"node_modules", ".next", "dist", "build", "__pycache__", ".venv", "venv"}
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix not in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".py"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in pattern_js.finditer(text):
            found.add(m.group(1))
        for m in pattern_py.finditer(text):
            found.add(m.group(1))
    return sorted(found)


def _scan_routes(repo: Path, framework: str) -> list[str]:
    """Best-effort route discovery per framework."""
    routes: set[str] = set()
    skip_dirs = {"node_modules", ".next", "dist", "build", "__pycache__", ".venv", "venv"}

    if framework in ("nextjs",):
        for path in repo.rglob("*"):
            if not path.is_file() or any(part in skip_dirs for part in path.parts):
                continue
            if path.name in ("route.ts", "route.js", "route.mjs"):
                # path is like /api/users/route.ts → /api/users
                parts = path.parts
                if "api" in parts:
                    idx = parts.index("api")
                    route = "/" + "/".join(parts[idx:-1])
                    routes.add(route)
            if path.name in ("page.tsx", "page.js"):
                parts = path.parts
                if "pages" in parts or "app" in parts or "src" in parts:
                    # find route relative to pages/app
                    for marker in ("pages", "app"):
                        if marker in parts:
                            idx = parts.index(marker)
                            route = "/" + "/".join(parts[idx:-1]).replace("[", ":").replace("]", "")
                            routes.add(route or "/")

    elif framework == "express":
        pattern = re.compile(r"""['"`](/[a-zA-Z0-9_\-:/\[\]*]+)['"`]""")
        for path in repo.rglob("*.js"):
            if any(part in skip_dirs for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in pattern.finditer(text):
                routes.add(m.group(1))

    elif framework == "fastapi":
        pattern = re.compile(r'@app\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']')
        for path in repo.rglob("*.py"):
            if any(part in skip_dirs for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in pattern.finditer(text):
                routes.add(m.group(2))

    return sorted(routes)


def detect_project(repo: Path) -> ProjectSpec:
    """Try node, python, go in that order."""
    for fn in (_detect_node, _detect_python, _detect_go):
        spec = fn(repo)
        if spec:
            return spec
    return ProjectSpec(
        repo_root=str(repo),
        language="unknown",
        framework="unknown",
        package_manager="unknown",
    )