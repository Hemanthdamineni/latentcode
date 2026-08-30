"""Lightweight HTTP server for the dashboard.

Exposes the findings + approval queue as JSON, and lets the dashboard
approve / reject / apply patches without shelling out to the CLI.

Routes:
    GET  /api/findings         — full findings.json
    GET  /api/queue            — pending + applied patches
    POST /api/queue/<id>/approve  — mark patch approved
    POST /api/queue/<id>/reject   — mark patch rejected
    POST /api/queue/<id>/apply    — apply patch + write to disk
    POST /api/rescan              — trigger a new scan
"""
from __future__ import annotations

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .project_detect import detect_project
from .static_analyzer import run_static_analysis
from .runtime_prober import run_runtime_probe
from .llm_reviewer import review_candidates, propose_patches
from .repair import ApprovalQueue, apply_patch
from .report.findings import write_findings


class Handler(BaseHTTPRequestHandler):
    findings_dir: Path = Path(".latentcode")
    repo_root: Path = Path(".")

    def log_message(self, format, *args):
        # Quieter logging
        sys.stderr.write(f"[serve] {self.address_string()} {format % args}\n")

    def _json(self, status: int, payload):
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return None
        body = self.rfile.read(length)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        if self.path == "/api/findings":
            p = self.findings_dir / "findings.json"
            if not p.exists():
                return self._json(404, {"error": "no findings yet"})
            return self._json(200, json.loads(p.read_text("utf-8")))
        if self.path == "/api/queue":
            q = self.findings_dir / "approval_queue.json"
            if not q.exists():
                return self._json(200, {"pending": [], "applied": []})
            return self._json(200, json.loads(q.read_text("utf-8")))
        if self.path == "/api/health":
            return self._json(200, {"status": "ok"})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/queue/approve":
            return self._approve()
        if self.path == "/api/queue/reject":
            return self._reject()
        if self.path == "/api/queue/apply":
            return self._apply()
        if self.path == "/api/rescan":
            return self._rescan()
        return self._json(404, {"error": "not found"})

    def _approve(self):
        body = self._read_json() or {}
        patch_id = body.get("id")
        if not patch_id:
            return self._json(400, {"error": "missing id"})
        queue = ApprovalQueue(self.findings_dir / "approval_queue.json")
        item = queue.approve(patch_id)
        if not item:
            return self._json(404, {"error": "patch not found or not pending"})
        return self._json(200, item)

    def _reject(self):
        body = self._read_json() or {}
        patch_id = body.get("id")
        reason = body.get("reason", "")
        if not patch_id:
            return self._json(400, {"error": "missing id"})
        queue = ApprovalQueue(self.findings_dir / "approval_queue.json")
        ok = queue.reject(patch_id, reason)
        if not ok:
            return self._json(404, {"error": "patch not found or not pending"})
        return self._json(200, {"rejected": patch_id})

    def _apply(self):
        body = self._read_json() or {}
        patch_id = body.get("id")
        if not patch_id:
            return self._json(400, {"error": "missing id"})
        queue = ApprovalQueue(self.findings_dir / "approval_queue.json")
        pending = queue.list_pending()
        item = next((p for p in pending if p["id"] == patch_id), None)
        if not item:
            return self._json(404, {"error": "patch not found or not pending"})
        results = apply_patch(item["patch"], self.repo_root, dry_run=False)
        return self._json(200, {"patch_id": patch_id, "results": results})

    def _rescan(self):
        spec = detect_project(self.repo_root)
        static = run_static_analysis(self.repo_root, spec)
        runtime = run_runtime_probe(self.repo_root, spec)
        findings = {
            "project": spec.to_dict(),
            "phases": {"static": static, "runtime": runtime},
        }
        write_findings(findings, self.findings_dir)
        return self._json(200, {"rescanned": True, "issues": len(static.get("issues", []))})


def serve(findings_dir: Path, repo_root: Path, host: str = "127.0.0.1", port: int = 7331):
    Handler.findings_dir = Path(findings_dir).resolve()
    Handler.repo_root = Path(repo_root).resolve()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"[serve] findings: {Handler.findings_dir}")
    print(f"[serve] repo:     {Handler.repo_root}")
    print(f"[serve] listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] shutting down")
        server.shutdown()