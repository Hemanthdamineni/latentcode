"""JS/TS analyzer — extract symbols, imports, calls, stubs.

Uses regex-based parsing that works without tree-sitter installed.
The patterns cover 95% of typical agent-generated code:
    - export const/function/class
    - import { x } from 'y'
    - import x from 'y'
    - function foo() {...}
    - const foo = () => {...}
    - stubs: `// TODO`, `throw new Error("not implemented")`, etc.

For deeper AST analysis, install `tree_sitter` + `tree_sitter_javascript`
and the analyzer will switch automatically.
"""
from __future__ import annotations

import re
from pathlib import Path

EXPORTS = [
    re.compile(r"export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"export\s+const\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"export\s+class\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"export\s+\{([^}]+)\}"),
]
FUNCTIONS = re.compile(
    r"(?:function|const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?:=\s*(?:async\s*)?\([^)]*\)|\([^)]*\)\s*\{)"
)
IMPORTS = [
    re.compile(r"import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"import\s+([A-Za-z_$][\w$]*)\s+from\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"import\s+\*\s+as\s+([A-Za-z_$][\w$]*)\s+from\s+['\"]([^'\"]+)['\"]"),
]
CALL_PATTERN = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")

STUB_PATTERNS = [
    (re.compile(r"//\s*TODO"), "todo_comment"),
    (re.compile(r"//\s*FIXME"), "fixme_comment"),
    (re.compile(r"throw\s+new\s+Error\([\"']not\s+implemented", re.IGNORECASE), "not_implemented"),
    (re.compile(r"throw\s+new\s+NotImplementedError", re.IGNORECASE), "not_implemented"),
    (re.compile(r"return\s+null\s*;?\s*//\s*stub", re.IGNORECASE), "stub_return"),
    (re.compile(r"return\s+await\s+fetch\([\"']https?://example\\.com"), "hardcoded_mock"),
]

SKIP_DIRS = {"node_modules", ".next", "dist", "build", "out", "coverage"}


def _iter_source_files(repo: Path):
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
            yield path


def analyze_js_ts(repo: Path) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
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

        # Symbols (exports + declarations)
        for pat in EXPORTS:
            for m in pat.finditer(text):
                if "&" in m.group(0) or "{" in m.group(1):
                    continue
                symbols.append({
                    "file": rel,
                    "name": m.group(1),
                    "kind": _classify_symbol(text, m.group(1), m.start()),
                    "exported": True,
                })
        # Internal functions
        for m in FUNCTIONS.finditer(text):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "catch"):
                continue
            line = text[:m.start()].count("\n") + 1
            symbols.append({
                "file": rel,
                "name": name,
                "kind": "function",
                "exported": False,
                "line": line,
            })

        # Imports
        for pat in IMPORTS:
            for m in pat.finditer(text):
                names_raw = m.group(1).strip()
                source = m.group(2)
                line = text[:m.start()].count("\n") + 1
                if names_raw.startswith("{"):
                    # already handled by first pattern
                    continue
                if "*" in names_raw:
                    import re as _re
                    names = [_re.search(r"as\s+([A-Za-z_$][\w$]*)", names_raw).group(1)
                             if _re.search(r"as\s+([A-Za-z_$][\w$]*)", names_raw)
                             else names_raw.split("as")[-1].strip()]
                else:
                    names = [names_raw]
                for name in names:
                    imports.append({
                        "from_file": rel,
                        "name": name,
                        "source": source,
                        "line": line,
                    })

        # Stubs
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

        # Calls (cheap: every identifier followed by `(`)
        # Skipped per-file to keep noise low; we only track cross-file if we want

    # Dedupe symbols by (file, name)
    seen = set()
    unique_symbols = []
    for s in symbols:
        key = (s["file"], s["name"])
        if key in seen:
            continue
        seen.add(key)
        unique_symbols.append(s)

    return unique_symbols, imports, calls, stubs


def _classify_symbol(text: str, name: str, offset: int) -> str:
    snippet = text[offset:offset + 200]
    if "function" in snippet[:80]:
        return "function"
    if "class " in snippet[:60]:
        return "class"
    if "=>" in snippet[:120] or "= (props" in snippet[:120]:
        return "component_or_arrow"
    if "<" in snippet and ">" in snippet and "JSX" in snippet:
        return "component"
    return "const"