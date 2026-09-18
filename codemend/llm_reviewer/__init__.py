"""LLM semantic reviewer — Judge + Proposer personas (split per audit).

Tooling-led: static + runtime findings are the input. The LLM does NOT
re-scan the codebase — it judges a curated set of candidates.

Two personas, deliberately separated:
    Judge     (judge.py)  — classifies + scores. No patch.
    Proposer  (proposer.py) — takes a Judge verdict and writes the diff.

Conflating them creates self-serving bias: the Judge who also proposes
is incentivized to under-report severity so the diff stays small.
"""
from __future__ import annotations

from .judge import review_candidates
from .proposer import propose_patches
from .prompts import (
    build_judge_prompt,
    build_proposer_prompt,
    JUDGE_SYSTEM_PROMPT,
    PROPOSER_SYSTEM_PROMPT,
)

__all__ = [
    "review_candidates",
    "propose_patches",
    "build_judge_prompt",
    "build_proposer_prompt",
    "JUDGE_SYSTEM_PROMPT",
    "PROPOSER_SYSTEM_PROMPT",
]