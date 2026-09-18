"""LLM Judge — classifies and scores candidates. Does NOT propose patches.

Per the agentic-system-design audit: the Judge and Proposer are split into
two personas to avoid self-serving bias (Judge who also proposes tends to
under-report severity so the diff stays small).

This module owns the Judge role. Patch generation lives in `proposer.py`.
"""
from __future__ import annotations

import json
import os
import random
import urllib.request
from pathlib import Path
from typing import Iterable

from .prompts import (
    JUDGE_SYSTEM_PROMPT,
    build_judge_prompt,
)


def review_candidates(
    candidates: list[dict],
    repo: Path,
    evidence_lookup: dict[str, dict] | None = None,
    provider: str = "auto",
    shuffle: bool = True,
    batch_size: int = 10,
) -> list[dict]:
    """Judge each candidate. Returns list of {candidate_id, verdict, ...}.

    provider: "auto" → try configured provider, fall back to heuristic.
              "heuristic" → skip LLM, use deterministic judgment.
              "openai" / "anthropic" / "ollama" → call that provider.
    shuffle:  randomize candidate order before LLM call (mitigates position bias).
    batch_size: max candidates per LLM call (batching reduces latency).
    """
    evidence_lookup = evidence_lookup or {}

    if shuffle:
        candidates = list(candidates)
        random.shuffle(candidates)

    if provider != "heuristic":
        verdicts = _try_provider_call(candidates, repo, evidence_lookup, provider, batch_size)
        if verdicts is not None:
            return verdicts

    # Fallback: heuristic judgment
    return [_heuristic_judge(c, evidence_lookup.get(c.get("id", ""), {})) for c in candidates]


def _try_provider_call(
    candidates: list[dict],
    repo: Path,
    evidence: dict,
    provider: str,
    batch_size: int,
) -> list[dict] | None:
    """Attempt an LLM call in batches. Returns None on failure so caller can fall back."""
    if provider == "auto":
        return None

    api_key = os.environ.get("OPENAI_API_KEY") if provider == "openai" else None
    if not api_key:
        return None

    try:
        client = _OpenAIClient(api_key=api_key)
        all_verdicts: list[dict] = []
        for batch in _chunked(candidates, batch_size):
            if len(batch) == 1:
                verdicts = client.judge_one(batch[0], evidence.get(batch[0].get("id", ""), {}), repo)
            else:
                verdicts = client.judge_batch(batch, evidence, repo)
            all_verdicts.extend(verdicts)
        return all_verdicts
    except Exception:
        return None


def _chunked(seq: list, n: int) -> Iterable[list]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class _OpenAIClient:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def _complete(self, messages: list[dict]) -> str:
        body = json.dumps({"model": self.model, "messages": messages, "temperature": 0.2}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

    def judge_one(self, candidate: dict, evidence: dict, repo: Path) -> list[dict]:
        code = _read_snippet(repo, candidate.get("file", ""), candidate.get("line", 0))
        prompt = build_judge_prompt(candidate, code, evidence)
        response = self._complete([
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        return [self._parse_verdict(response, candidate)]

    def judge_batch(self, batch: list[dict], evidence: dict, repo: Path) -> list[dict]:
        """Judge multiple candidates in a single LLM call.

        Position-bias mitigation: candidates are pre-shuffled by the caller.
        We still present them in a numbered list to make the model re-read each.
        """
        items = []
        for c in batch:
            code = _read_snippet(repo, c.get("file", ""), c.get("line", 0))
            items.append({
                "candidate": c,
                "snippet": code,
                "evidence": evidence.get(c.get("id", ""), {}),
            })
        user_prompt = _format_batch_prompt(items)
        response = self._complete([
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT + "\n\nYou will see multiple candidates. Return a JSON array, one object per candidate, in the same order."},
            {"role": "user", "content": user_prompt},
        ])
        return self._parse_batch(response, batch)

    def _parse_verdict(self, response: str, candidate: dict) -> dict:
        try:
            obj = json.loads(response)
            obj["candidate_id"] = candidate.get("id")
            return obj
        except json.JSONDecodeError:
            return {
                "candidate_id": candidate.get("id"),
                "verdict": "needs-info",
                "reasoning": "could not parse LLM response",
            }

    def _parse_batch(self, response: str, batch: list[dict]) -> list[dict]:
        try:
            arr = json.loads(response)
            if not isinstance(arr, list):
                return [self._parse_verdict(response, c) for c in batch]
            # Pad/truncate to match batch length
            while len(arr) < len(batch):
                arr.append({"verdict": "needs-info", "reasoning": "missing from response"})
            out = []
            for c, obj in zip(batch, arr[:len(batch)]):
                obj = dict(obj)
                obj["candidate_id"] = c.get("id")
                out.append(obj)
            return out
        except json.JSONDecodeError:
            return [self._parse_verdict(response, c) for c in batch]


def _format_batch_prompt(items: list[dict]) -> str:
    parts = ["You will judge the following candidates. Return a JSON array (one object per candidate, in the same order as listed).\n"]
    for i, item in enumerate(items, 1):
        c = item["candidate"]
        parts.append(f"\n## Candidate {i}: id={c.get('id', '?')}")
        parts.append(f"Category: {c.get('category', '?')} / {c.get('subtype', '?')}")
        parts.append(f"Location: {c.get('file', '?')}:{c.get('line', '?')}")
        parts.append("Code:")
        parts.append(f"```\n{item['snippet']}\n```")
        if item["evidence"]:
            parts.append(f"Evidence: {item['evidence']}")
    return "\n".join(parts)


def _heuristic_judge(candidate: dict, evidence: dict) -> dict:
    """Deterministic Judge when no LLM is available.

    Strictly classifies + scores. Does NOT produce a patch — that is the
    Proposer's job, which the deterministic fallback in `patch_proposer.py`
    covers.
    """
    cat = candidate.get("category", "")
    subtype = candidate.get("subtype", "")
    severity = candidate.get("severity", 0.5)

    if subtype == "not_implemented":
        verdict, classification, severity = "real", "stub", max(severity, 0.85)
        reasoning = "Code raises NotImplementedError or similar — clear placeholder."
        suggested = "implement"
    elif subtype == "todo_comment":
        verdict, classification = "real", "stub"
        severity = max(severity, 0.6)
        reasoning = "TODO comment indicates incomplete implementation."
        suggested = "implement"
    elif subtype == "dead_export":
        verdict, classification = "real", "disconnected"
        reasoning = "Exported symbol has no importer in the project. May be public API or genuinely dead."
        suggested = "delete or wire"
    elif subtype == "env_var_missing":
        verdict, classification = "real", "broken-integration"
        severity = max(severity, 0.6)
        reasoning = f"Environment variable referenced in code but not declared in any .env file."
        suggested = "add to .env.example"
    else:
        verdict, classification = "needs-info", "unknown"
        reasoning = "Heuristic reviewer requires an LLM to judge this category."
        suggested = "needs LLM"

    return {
        "candidate_id": candidate.get("id"),
        "verdict": verdict,
        "classification": classification,
        "severity": severity,
        "reasoning": reasoning,
        "suggested_fix_direction": suggested,
        "judge_mode": "heuristic",
        "file": candidate.get("file"),
        "line": candidate.get("line"),
        "symbol": candidate.get("symbol"),
        "var": candidate.get("var"),
        "files": candidate.get("files"),
        "evidence": candidate.get("evidence"),
        # Forward repair_scope so the Proposer knows its allowed files
        "repair_scope": candidate.get("repair_scope"),
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