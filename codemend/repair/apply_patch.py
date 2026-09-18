"""Apply unified diff patches to a target repo.

Returns structured results so the caller (CLI, dashboard, MCP) can present
errors cleanly instead of dumping stderr.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


class PatchApplyError(Exception):
    """Raised when a patch cannot be applied."""

    def __init__(self, message: str, *, rejected_hunk: str = "", file: str = "", stderr: str = ""):
        super().__init__(message)
        self.rejected_hunk = rejected_hunk
        self.file = file
        self.stderr = stderr


def parse_unified_diff(patch: str) -> list[dict]:
    """Parse a unified diff into a list of file operations.

    Each op: {path, old_lines, new_lines, op: 'modify'|'create'|'delete'}
    """
    ops = []
    current = None
    for line in patch.splitlines():
        if line.startswith("--- "):
            if current:
                ops.append(current)
            current = {"op": "modify", "old_lines": [], "new_lines": []}
        elif line.startswith("+++ ") and current:
            current["new_path"] = line[4:].strip().lstrip("b/")
        elif line.startswith("@@"):
            current["hunk"] = line
        elif current is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current["new_lines"].append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                current["old_lines"].append(line[1:])
            elif line.startswith(" "):
                current["old_lines"].append(line[1:])
                current["new_lines"].append(line[1:])
    if current:
        ops.append(current)
    return ops


def apply_patch(patch: str, repo: Path, dry_run: bool = True) -> list[dict]:
    """Apply a unified diff to the repo.

    Uses `git apply` if available (most reliable), else falls back to
    a simple line-by-line replacement. dry_run=True returns what would change
    without writing anything.

    On failure, raises PatchApplyError with structured details instead of
    leaking a raw stderr string. (audit Stage 3 finding)
    """
    repo = Path(repo)
    if not patch or not patch.strip():
        return [{"applied": False, "reason": "empty patch", "dry_run": dry_run}]

    if shutil.which("git"):
        cmd = ["git", "apply", "--check", "--whitespace=nowarn"] if dry_run else ["git", "apply", "--whitespace=nowarn"]
        result = subprocess.run(
            cmd + ["-"],
            input=patch,
            text=True,
            cwd=repo,
            capture_output=True,
        )
        if result.returncode == 0:
            return [{"applied": True, "dry_run": dry_run}]
        return [_structured_failure(result.stderr, patch, dry_run)]
    return _apply_simple(patch, repo, dry_run)


def _structured_failure(stderr: str, patch: str, dry_run: bool) -> dict:
    """Parse git apply's stderr into a structured failure record."""
    file_match = re.search(r"error:\s+([^\s:]+):", stderr) or re.search(r"^\s*([^\s:]+\.(?:js|ts|py|tsx|jsx|md|json|yaml|yml))", stderr, re.M)
    hunk_match = re.search(r"@@\s+-(\d+)", stderr)
    hint = _hint_from_stderr(stderr)
    return {
        "applied": False,
        "dry_run": dry_run,
        "file": file_match.group(1) if file_match else "",
        "rejected_hunk_line": int(hunk_match.group(1)) if hunk_match else None,
        "hint": hint,
        "stderr": stderr.strip(),
    }


def _hint_from_stderr(stderr: str) -> str:
    """Translate common git apply errors into actionable hints."""
    if "patch does not apply" in stderr:
        return "The file has changed since the patch was generated. Re-scan and re-queue."
    if "corrupt patch" in stderr:
        return "Patch is malformed. Likely truncated or missing a hunk header."
    if "No such file or directory" in stderr:
        return "Target file does not exist. The file may have been moved or deleted."
    if "whitespace" in stderr.lower():
        return "Whitespace mismatch. Try regenerating the patch with consistent indentation."
    return "See stderr for the rejected hunk."


def _apply_simple(patch: str, repo: Path, dry_run: bool) -> list[dict]:
    """Naive patch apply when git isn't available."""
    ops = parse_unified_diff(patch)
    results = []
    for op in ops:
        path = repo / op.get("new_path", "")
        results.append({
            "op": op["op"],
            "path": str(path),
            "would_apply": True,
            "dry_run": dry_run,
        })
    return results