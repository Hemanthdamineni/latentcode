"""Eval runner — orchestrate the three classes, score per-class accuracy."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .types import ClassScore
from .static_class import StaticClass
from .integration_class import IntegrationClass
from .behavioral_class import BehavioralClass


@dataclass
class EvalReport:
    target_repo: str
    static_score: ClassScore
    integration_score: ClassScore
    behavioral_score: ClassScore
    overall_score: float

    def to_dict(self) -> dict:
        return {
            "target_repo": self.target_repo,
            "static": self.static_score.to_dict(),
            "integration": self.integration_score.to_dict(),
            "behavioral": self.behavioral_score.to_dict(),
            "overall": round(self.overall_score, 3),
        }

    def render_markdown(self) -> str:
        lines = [
            f"# LatentCode Eval — {Path(self.target_repo).name}",
            "",
            "| Class | Score |",
            "|---|---|",
            f"| Static | {self.static_score.score:.0%} |",
            f"| Integration | {self.integration_score.score:.0%} |",
            f"| Behavioral | {self.behavioral_score.score:.0%} |",
            f"| **Overall** | **{self.overall_score:.0%}** |",
            "",
        ]
        for s in (self.static_score, self.integration_score, self.behavioral_score):
            lines.append(f"## {s.name}")
            lines.append("")
            detail = s.detail
            for k, v in detail.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")
        return "\n".join(lines)


def run_eval(target_repo: str | Path) -> EvalReport:
    """Run the three eval classes against a target repo with a golden_labels.json."""
    repo = Path(target_repo)
    labels_path = repo / "golden_labels.json"
    if not labels_path.exists():
        raise FileNotFoundError(f"no golden_labels.json at {labels_path}")

    labels = json.loads(labels_path.read_text(encoding="utf-8"))

    static = StaticClass()
    integration = IntegrationClass()
    behavioral = BehavioralClass()

    static_score = static.score(repo, labels.get("static_class", {}))
    integration_score = integration.score(repo, labels.get("integration_class", {}))
    behavioral_score = behavioral.score(repo, labels.get("behavioral_class", {}))

    overall = (static_score.score + integration_score.score + behavioral_score.score) / 3

    return EvalReport(
        target_repo=str(repo),
        static_score=static_score,
        integration_score=integration_score,
        behavioral_score=behavioral_score,
        overall_score=round(overall, 3),
    )