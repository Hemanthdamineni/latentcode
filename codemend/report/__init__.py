"""Report writers — findings.json + findings.md."""
from __future__ import annotations

from pathlib import Path

from .findings import write_findings

__all__ = ["write_findings"]