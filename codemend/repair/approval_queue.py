"""Approval queue — pending patches that need human sign-off.

Persists to disk so the dashboard and CLI can review + act.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path


class ApprovalQueue:
    def __init__(self, queue_path: Path):
        self.path = queue_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"pending": [], "applied": []}, indent=2))

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict):
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, candidate: dict, patch: str, source: str = "llm") -> str:
        data = self._read()
        item_id = str(uuid.uuid4())[:8]
        data["pending"].append({
            "id": item_id,
            "candidate": candidate,
            "patch": patch,
            "patch_source": source,
            "status": "pending",
        })
        self._write(data)
        return item_id

    def approve(self, item_id: str) -> dict | None:
        data = self._read()
        for i, item in enumerate(data["pending"]):
            if item["id"] == item_id:
                item["status"] = "approved"
                data["applied"].append(data["pending"].pop(i))
                self._write(data)
                return item
        return None

    def reject(self, item_id: str, reason: str = "") -> bool:
        data = self._read()
        for i, item in enumerate(data["pending"]):
            if item["id"] == item_id:
                item["status"] = "rejected"
                item["rejection_reason"] = reason
                data["pending"].pop(i)
                self._write(data)
                return True
        return False

    def list_pending(self) -> list[dict]:
        return self._read().get("pending", [])

    def list_applied(self) -> list[dict]:
        return self._read().get("applied", [])