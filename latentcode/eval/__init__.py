"""Eval harness — three-class evaluation against golden labels.

Per audit revision Challenge 4: the audit's single-class acceptance
criterion (planted static defects only) is too narrow. LatentCode's
hardest problem is *semantic* — the agent says the feature is
implemented but it isn't. That requires three classes of evaluation:

  static_class       — does the analyzer find the planted syntax-level
                       defects (stubs, dead exports, missing env vars)?
  integration_class  — does the analyzer catch UI/API/handler wiring gaps
                       that span multiple files?
  behavioral_class   — does the verification framework correctly identify
                       which declared actions pass and which fail?

The eval harness reads `golden_labels.json` from each target repo and
computes precision/recall per class.
"""
from __future__ import annotations

from .runner import run_eval, EvalReport
from .static_class import StaticClass
from .integration_class import IntegrationClass
from .behavioral_class import BehavioralClass

__all__ = [
    "run_eval",
    "EvalReport",
    "StaticClass",
    "IntegrationClass",
    "BehavioralClass",
]