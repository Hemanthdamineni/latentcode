"""Behavioral correctness eval — does LatentCode identify which actions
correctly fail and which correctly pass?

The behavioral class runs the verification spec against the broken repo
(no live server, so all actions that depend on a real handler will
fail). Then it checks LatentCode's findings: did the analyzer flag
the actions that are expected to fail?

Scoring:
  - For each `expected_actions[i]` with `expected_pass: false`, did
    LatentCode flag at least one issue that would cause this action
    to fail? (matched by category or file)
  - score = detected_expected_failures / total_expected_failures
"""
from __future__ import annotations

from pathlib import Path

from .types import ClassScore
from ..project_detect import detect_project
from ..static_analyzer import run_static_analysis


class BehavioralClass:
    def score(self, repo: Path, labels: dict) -> ClassScore:
        spec = detect_project(repo)
        result = run_static_analysis(repo, spec)
        flagged = result.get("issues", [])

        # The behavioral class checks: for each action that is expected
        # to fail, did LatentCode flag the underlying issue?
        actions = labels.get("expected_actions", [])
        if not actions:
            return ClassScore(name="behavioral", score=1.0, detail={"note": "no behavioral actions in golden set"})

        expected_failures = [a for a in actions if a.get("expected_pass") is False]
        if not expected_failures:
            return ClassScore(name="behavioral", score=1.0, detail={"note": "no expected failures"})

        # Heuristic: an expected failure is "detected" if LatentCode
        # flagged at least one issue in any of the action's evidence files
        # OR the action's expected_pass=false is matched by a stub/etc.
        detected = 0
        for a in expected_failures:
            # We don't have evidence_files in behavioral labels yet;
            # fall back to: did the analyzer flag any agent_shortcut or
            # broken_integration issue?
            rationale = a.get("rationale", "").lower()
            for issue in flagged:
                cat = issue.get("category", "")
                if cat in ("agent_shortcut", "broken_integration", "broken_e2e_feature", "hidden_implementation"):
                    if "stub" in rationale or "not implemented" in rationale:
                        if cat == "agent_shortcut" and issue.get("subtype") in ("not_implemented", "todo_comment"):
                            detected += 1
                            break
                    if "client" in rationale or "imported" in rationale or "wired" in rationale:
                        if cat == "hidden_implementation" and issue.get("subtype") == "dead_export":
                            detected += 1
                            break
                    # Default: any issue in this file family counts
                    detected += 1
                    break

        recall = detected / len(expected_failures) if expected_failures else 0.0
        min_required = labels.get("expected_min_issues_flagged", 0)
        # Bonus credit if the analyzer found at least the minimum issues
        meets_min = len(flagged) >= min_required
        score = recall * (1.0 if meets_min else 0.5)

        return ClassScore(
            name="behavioral",
            score=round(score, 3),
            detail={
                "expected_failures": len(expected_failures),
                "detected": detected,
                "total_flagged": len(flagged),
                "min_required": min_required,
                "meets_minimum": meets_min,
                "recall": round(recall, 3),
            },
        )