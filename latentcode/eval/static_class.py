"""Static correctness eval — does LatentCode find the planted syntax defects?

The static class is the simplest: run the analyzer, compare its output
against `golden_labels.json -> static_class -> expected_issues`.

Scoring:
  - For each `expected_issues[i]` with `must_be_flagged: true`, check
    if LatentCode's issues contain a match (file + subtype match).
  - precision = flagged_and_correct / total_flagged
  - recall = flagged_and_correct / total_expected_to_flag
  - score = (precision + recall) / 2  (F1)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .types import ClassScore
from ..project_detect import detect_project
from ..static_analyzer import run_static_analysis


class StaticClass:
    def score(self, repo: Path, labels: dict) -> ClassScore:
        spec = detect_project(repo)
        result = run_static_analysis(repo, spec)
        flagged = result.get("issues", [])

        # Convert flagged issues to a comparable set: (file, subtype) tuples
        # (we ignore line since the analyzer sometimes reports 0 for file-level)
        flagged_set = {(i.get("file", ""), i.get("subtype", "")) for i in flagged}

        expected_to_flag = labels.get("expected_issues", [])
        must_not_flag = labels.get("must_not_flag", [])

        true_positives = 0
        for e in expected_to_flag:
            if not e.get("must_be_flagged", True):
                continue
            key = (e.get("file", ""), e.get("subtype", ""))
            if key in flagged_set:
                true_positives += 1

        false_positives = 0
        for m in must_not_flag:
            key = (m.get("file", ""), "")
            # Match if the analyzer flagged this file with any subtype
            for (f, _) in flagged_set:
                if f == m.get("file", ""):
                    false_positives += 1
                    break

        total_flagged = len(flagged)
        total_expected = sum(1 for e in expected_to_flag if e.get("must_be_flagged", True))

        precision = true_positives / total_flagged if total_flagged else 0.0
        recall = true_positives / total_expected if total_expected else 0.0
        score = (precision + recall) / 2 if (precision + recall) > 0 else 0.0

        return ClassScore(
            name="static",
            score=round(score, 3),
            detail={
                "true_positives": true_positives,
                "false_positives": false_positives,
                "total_flagged": total_flagged,
                "total_expected": total_expected,
                "precision": round(precision, 3),
                "recall": round(recall, 3),
            },
        )