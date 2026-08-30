"""LLM Proposer — takes Judge verdicts and emits unified diffs.

Per the agentic-system-design audit (Stage 7): the Proposer is a separate
persona from the Judge. This eliminates self-serving bias (the Judge who
also proposes is incentivized to under-report severity) and makes each
role auditable independently.

This module also keeps a deterministic fallback for the simple cases so
the user has something concrete to review when no LLM is configured.

SCOPE VALIDATION (per revision Challenge 1):
- Each verdict carries a `repair_scope` computed by BFS through the
  issue graph (latentcode.static_analyzer.issue_graph.compute_repair_scope).
- The Proposer may touch ANY file in the scope, not just the candidate's
  file. This is what enables multi-file E2E repairs.
- After the LLM/deterministic patch is generated, we extract the files
  the diff touches and verify each is in the scope. Out-of-scope files
  cause the patch to be rejected (empty patch + clear `risks` message).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

from .prompts import (
    PROPOSER_SYSTEM_PROMPT,
    build_proposer_prompt,
)


def propose_patches(verdicts: list[dict], repo: Path) -> list[dict]:
    """For each verdict, ensure a patch exists and is scope-compliant.

    Tries the LLM Proposer for `real` verdicts. Falls back to deterministic
    templates when no LLM is available. Either way, the final patch is
    validated against the verdict's repair_scope.

    Each enriched verdict gets:
      - patch: unified diff (or empty string)
      - patch_summary: 1-sentence description
      - risks: what could go wrong
      - test_suggestion: how a human could verify
      - files_modified: list of files the patch touches
      - scope_violation: True if patch was rejected for touching out-of-scope files
      - patch_source: "llm" | "deterministic"
    """
    repo = Path(repo)
    enriched: list[dict] = []

    llm = _make_llm_client()

    for v in verdicts:
        if v.get("verdict") != "real":
            v2 = dict(v)
            v2["patch"] = ""
            v2["files_modified"] = []
            v2["scope_violation"] = False
            v2["patch_source"] = "n/a"
            enriched.append(v2)
            continue

        scope = v.get("repair_scope") or {"files": [v.get("file", "unknown")], "depth": 0, "rationale": "fallback"}
        scope_files = set(scope.get("files", []))

        # Try LLM Proposer first
        patch_obj = None
        if llm is not None:
            try:
                patch_obj = llm.propose(v, repo, scope)
                source = "llm"
            except Exception:
                patch_obj = None

        if patch_obj is None or not patch_obj.get("patch"):
            patch_obj = _deterministic_patch(v, repo, scope)
            source = "deterministic"

        # Scope validation
        files_touched = _extract_files_from_patch(patch_obj.get("patch", ""))
        out_of_scope = sorted(set(files_touched) - scope_files)
        scope_violation = bool(out_of_scope)

        if scope_violation:
            # Reject the patch — the Proposer touched files outside its scope.
            # This is the safety boundary the audit asked for: scope is
            # calculated, not assumed; the LLM can't silently expand it.
            patch_obj = {
                "patch": "",
                "patch_summary": f"patch rejected: touched {out_of_scope} which is outside the repair scope {sorted(scope_files)}",
                "risks": f"proposed patch modifies files not in the calculated repair scope; refusing to apply. Set --force-extra-files to override.",
                "test_suggestion": "review the scope or generate a patch manually",
                "files_modified": [],
            }
            source = "rejected (out-of-scope)"

        v2 = dict(v)
        v2["patch"] = patch_obj.get("patch", "")
        v2["patch_summary"] = patch_obj.get("patch_summary", "")
        v2["risks"] = patch_obj.get("risks", "unknown")
        v2["test_suggestion"] = patch_obj.get("test_suggestion", "manual review")
        v2["files_modified"] = files_touched
        v2["scope_violation"] = scope_violation
        v2["patch_source"] = source
        enriched.append(v2)

    return enriched


def _extract_files_from_patch(patch: str) -> list[str]:
    """Pull the list of files a unified diff touches.

    Matches `+++ b/path/to/file` lines (the canonical target line in a
    unified diff). Skips `/dev/null` (file deletion).
    """
    files = []
    for line in patch.splitlines():
        m = re.match(r"^\+\+\+\s+(?:b/)?(\S+)", line)
        if m:
            f = m.group(1)
            if f != "/dev/null" and f not in files:
                files.append(f)
    return files


def _make_llm_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return _ProposerClient(api_key=api_key)


class _ProposerClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def propose(self, verdict: dict, repo: Path, repair_scope: dict) -> dict:
        file_path = verdict.get("file", "unknown")
        code = _read_snippet(repo, file_path, verdict.get("line", 1))
        prompt = build_proposer_prompt(verdict, code, file_path, repair_scope)
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": PROPOSER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        response = data["choices"][0]["message"]["content"]
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"patch": "", "patch_summary": "could not parse", "risks": "unknown"}


def _deterministic_patch(verdict: dict, repo: Path, repair_scope: dict) -> dict:
    """Generate a patch for simple, well-understood cases.

    The Judge's `suggested_fix_direction` and `classification` guide the
    template selection. The repair_scope is passed so the template can
    stay within bounds. Real production use should rely on the LLM to
    synthesize non-trivial patches.
    """
    classification = verdict.get("classification", "")
    direction = verdict.get("suggested_fix_direction", "")

    if classification == "disconnected" or "delete" in direction:
        file_path = verdict.get("file", "unknown")
        symbol = verdict.get("symbol") or "unknown"
        if symbol == "unknown":
            cid = verdict.get("candidate_id", "")
            parts = cid.split("::")
            if len(parts) >= 2:
                symbol = parts[1] if parts[1] else parts[0]
        return {
            "patch": (
                f"--- a/{file_path}\n"
                f"+++ b/{file_path}\n"
                f"@@ -1,1 +1,1 @@\n"
                f"-// TODO: confirm and remove unused export `{symbol}`\n"
                f"+// [LatentCode] removed unused export `{symbol}`\n"
            ),
            "patch_summary": f"Mark `{symbol}` as removed (heuristic placeholder).",
            "risks": "Symbol may be used via reflection, dynamic import, or as a public API. Verify before merging.",
            "test_suggestion": "Run the build; if any module still imports this symbol, revert.",
        }

    if classification == "broken-integration" or "add-env" in direction:
        var = verdict.get("var", "")
        files = verdict.get("files", [])
        if var:
            return {
                "patch": (
                    f"--- a/.env.example\n"
                    f"+++ b/.env.example\n"
                    f"@@ -0,0 +1,2 @@\n"
                    f"+# Added by LatentCode — referenced in: {', '.join(files[:3]) or 'unknown'}\n"
                    f"+{var}=\n"
                ),
                "patch_summary": f"Add `{var}` to .env.example so the integration at least declares the dependency.",
                "risks": "Real value still missing from .env. Just documents the requirement.",
                "test_suggestion": "Set the value in .env and re-run the failing path.",
            }

    if classification == "stub" or "implement" in direction:
        file_path = verdict.get("file", "unknown")
        line = verdict.get("line", 1) or 1
        return {
            "patch": (
                f"--- a/{file_path}\n"
                f"+++ b/{file_path}\n"
                f"@@ -{line},1 +{line},1 @@\n"
                f"-throw new Error(\"not implemented\"); // TODO: implement\n"
                f"+// [LatentCode] stub removed — please implement this handler\n"
            ),
            "patch_summary": "Comment out the throwing stub so callers stop 500-ing; explicitly mark the gap.",
            "risks": "Replaces a hard error with a silent no-op. Caller may now succeed with empty data.",
            "test_suggestion": "Add a test that exercises this path with real inputs.",
        }

    return {
        "patch": "",
        "patch_summary": "Deterministic fallback has no template for this category.",
        "risks": "no patch generated",
        "test_suggestion": "manual review",
    }


def _read_snippet(repo: Path, file_path: str, line: int, context: int = 10) -> str:
    p = repo / file_path
    if not p.exists():
        return f"(file not found: {file_path})"
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return f"(cannot read: {file_path})"
    if not line or line <= 0:
        line = 1
    start = max(0, line - context - 1)
    end = min(len(lines), line + context)
    return "\n".join(lines[start:end])