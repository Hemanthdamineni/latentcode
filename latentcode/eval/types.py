"""Shared types for the eval harness.

Kept separate from runner.py to avoid circular imports.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClassScore:
    name: str
    score: float
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "score": self.score, "detail": self.detail}