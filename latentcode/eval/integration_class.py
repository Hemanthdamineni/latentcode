"""Integration correctness eval — does LatentCode catch UI/API/handler gaps?

Integration issues span multiple files. The eval checks: for each
golden integration issue, did LatentCode flag at least one issue
whose evidence_files match?

This is a softer check than static (because LatentCode's existing
detectors are mostly file-level). A future enhancement: explicitly
add an `integration_wiring` detector. For v1, we measure what we have.
"""
from __future__ import annotations

from pathlib import Path

from .types import ClassScore
from ..project_detect import detect_project
from ..static_analyzer import run_static_analysis


class IntegrationClass:
    def score(self, repo: Path, labels: dict) -> ClassScore:
        spec = detect_project(repo)
        result = run_static_analysis(repo, spec)
        flagged = result.get("issues", [])

        # Build a per-file flag set so we can check overlap
        flagged_files: set[str] = set()
        for i in flagged:
            if i.get("file"):
                flagged_files.add(i["file"])
            if i.get("files"):
                flagged_files.update(i["files"])

        expected = labels.get("expected_issues", [])
        if not expected:
            return ClassScore(name="integration", score=1.0, detail={"note": "no integration issues in golden set"})

        detected = 0
        for e in expected:
            if not e.get("must_be_flagged", True):
                continue
            evidence = set(e.get("evidence_files", []))
            # Did LatentCode flag at least one file in the evidence set?
            if evidence & flagged_files:
                detected += 1

        recall = detected / len(expected) if expected else 0.0
        # No precision check here — without a true "should not flag" list,
        # we measure recall only. Score = recall.
        return ClassScore(
            name="integration",
            score=round(recall, 3),
            detail={
                "expected_integration_issues": len(expected),
                "detected": detected,
                "recall": round(recall, 3),
                "note": "integration class measures recall only; add 'must_not_flag' for precision",
            },
        )