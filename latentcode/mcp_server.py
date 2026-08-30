"""LatentCode MCP server.

Exposes the analysis + repair pipeline as MCP tools so any agent
(Claude Code, Cursor, custom harnesses) can drive LatentCode.

Tools:
    latentcode_scan(repo, phase, judge)
    latentcode_judge(repo)
    latentcode_regress(repo, baseline_path)
    latentcode_approve(findings_dir, patch_id)
    latentcode_reject(findings_dir, patch_id, reason)
    latentcode_apply(findings_dir, patch_id)
    latentcode_queue(findings_dir)
    latentcode_summary(findings_dir)

Run:
    latentcode-mcp                # stdio transport
    latentcode-mcp --port 7332    # SSE transport (if mcp[server] installed)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .project_detect import detect_project
from .static_analyzer import run_static_analysis
from .runtime_prober import run_runtime_probe
from .llm_reviewer import review_candidates, propose_patches
from .report.findings import write_findings
from .repair import ApprovalQueue, apply_patch, run_regression_check


def _read_findings(findings_dir: str) -> dict:
    p = Path(findings_dir) / "findings.json"
    if not p.exists():
        return {"error": f"no findings at {p}"}
    return json.loads(p.read_text("utf-8"))


def _read_queue(findings_dir: str) -> dict:
    p = Path(findings_dir) / "approval_queue.json"
    if not p.exists():
        return {"pending": [], "applied": []}
    return json.loads(p.read_text("utf-8"))


def tool_scan(repo: str, phase: str = "all", judge: str | None = None, allow_remote: bool = False) -> dict:
    """Scan a repo for latent issues.

    Args:
        repo: absolute path to repo
        phase: static | runtime | all
        judge: heuristic | llm | None
        allow_remote: permit runtime prober to bind non-loopback (off by default)

    Returns: { project, static, runtime, issues, summary }
    """
    repo_p = Path(repo).resolve()
    if not repo_p.exists():
        return {"error": f"{repo} does not exist"}

    spec = detect_project(repo_p)
    findings: dict = {"project": spec.to_dict(), "phases": {}}

    if phase in ("static", "all"):
        static = run_static_analysis(repo_p, spec)
        findings["phases"]["static"] = static

    if phase in ("runtime", "all"):
        runtime = run_runtime_probe(repo_p, spec, allow_remote=allow_remote)
        findings["phases"]["runtime"] = runtime

    if judge and findings["phases"].get("static", {}).get("issues"):
        candidates = [
            {**i, "id": f"{i.get('file','?')}::{i.get('line',0)}::{i.get('subtype','?')}"}
            for i in findings["phases"]["static"]["issues"]
        ]
        verdicts = review_candidates(candidates, repo_p, provider=judge)
        verdicts = propose_patches(verdicts, repo_p)
        findings["phases"]["review"] = {"verdicts": verdicts}

    out_dir = repo_p / ".latentcode"
    write_findings(findings, out_dir)

    return {
        "findings_path": str(out_dir / "findings.json"),
        "issue_count": len(findings["phases"].get("static", {}).get("issues", [])),
        "summary": findings.get("phases", {}).get("static", {}).get("issues", []),
    }


def tool_judge(repo: str) -> dict:
    """Re-run the LLM/heuristic judge on a previously-scanned repo's candidates."""
    repo_p = Path(repo).resolve()
    findings = _read_findings(str(repo_p / ".latentcode"))
    issues = findings.get("phases", {}).get("static", {}).get("issues", [])
    if not issues:
        return {"error": "no issues in saved findings — run scan first"}
    candidates = [
        {**i, "id": f"{i.get('file','?')}::{i.get('line',0)}::{i.get('subtype','?')}"}
        for i in issues
    ]
    verdicts = review_candidates(candidates, repo_p, provider="heuristic")
    verdicts = propose_patches(verdicts, repo_p)
    queue = ApprovalQueue(repo_p / ".latentcode" / "approval_queue.json")
    queued = 0
    for cand, v in zip(candidates, verdicts):
        if v.get("verdict") == "real" and v.get("patch"):
            queue.add(cand, v["patch"], source=v.get("patch_source", "unknown"))
            queued += 1
    return {"verdicts": verdicts, "queued": queued}


def tool_regress(repo: str, baseline_path: str | None = None) -> dict:
    """Re-run scan and compare to a baseline findings.json."""
    repo_p = Path(repo).resolve()
    baseline = Path(baseline_path) if baseline_path else repo_p / ".latentcode" / "findings.json"
    if not baseline.exists():
        return {"error": f"baseline not found at {baseline}"}
    pre = json.loads(baseline.read_text("utf-8"))
    spec = detect_project(repo_p)
    return run_regression_check(repo_p, spec, pre)


def tool_approve(findings_dir: str, patch_id: str) -> dict:
    q = ApprovalQueue(Path(findings_dir) / "approval_queue.json")
    item = q.approve(patch_id)
    if not item:
        return {"error": f"patch {patch_id} not found or not pending"}
    return item


def tool_reject(findings_dir: str, patch_id: str, reason: str = "") -> dict:
    q = ApprovalQueue(Path(findings_dir) / "approval_queue.json")
    ok = q.reject(patch_id, reason)
    if not ok:
        return {"error": f"patch {patch_id} not found or not pending"}
    return {"rejected": patch_id, "reason": reason}


def tool_apply(findings_dir: str, patch_id: str) -> dict:
    q = ApprovalQueue(Path(findings_dir) / "approval_queue.json")
    pending = q.list_pending()
    item = next((p for p in pending if p["id"] == patch_id), None)
    if not item:
        return {"error": f"patch {patch_id} not found or not pending"}
    repo = Path(findings_dir).parent
    results = apply_patch(item["patch"], repo, dry_run=False)
    return {"patch_id": patch_id, "results": results}


def tool_queue(findings_dir: str) -> dict:
    return _read_queue(findings_dir)


def tool_summary(findings_dir: str) -> dict:
    f = _read_findings(findings_dir)
    return {
        "project": f.get("project"),
        "summary": f.get("summary"),
        "generated_at": f.get("generated_at"),
    }


# ---------------------------------------------------------------------------
# MCP transport — minimal stdio JSON-RPC implementation that works without
# requiring the `mcp` package. Compatible with the same tool schema that
# official MCP servers expose, so clients (Claude Code, Cursor, etc.) can
# connect with no extra adapter.
# ---------------------------------------------------------------------------

TOOLS = {
    "latentcode_scan": {
        "description": "Scan a repo for latent defects. Returns findings path and issue count.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "absolute path to repo"},
                "phase": {"type": "string", "enum": ["static", "runtime", "all"], "default": "all"},
                "judge": {"type": "string", "enum": ["heuristic", "llm"], "description": "judge mode"},
                "allow_remote": {"type": "boolean", "description": "permit non-loopback binding during runtime probe", "default": False},
            },
            "required": ["repo"],
        },
        "handler": lambda args: tool_scan(args["repo"], args.get("phase", "all"), args.get("judge"), args.get("allow_remote", False)),
    },
    "latentcode_judge": {
        "description": "Run the judge on existing scan results, queue patches.",
        "inputSchema": {
            "type": "object",
            "properties": {"repo": {"type": "string"}},
            "required": ["repo"],
        },
        "handler": lambda args: tool_judge(args["repo"]),
    },
    "latentcode_regress": {
        "description": "Re-scan and compare to a baseline findings.json.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "baseline_path": {"type": "string"},
            },
            "required": ["repo"],
        },
        "handler": lambda args: tool_regress(args["repo"], args.get("baseline_path")),
    },
    "latentcode_approve": {
        "description": "Approve a pending patch in the queue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "findings_dir": {"type": "string"},
                "patch_id": {"type": "string"},
            },
            "required": ["findings_dir", "patch_id"],
        },
        "handler": lambda args: tool_approve(args["findings_dir"], args["patch_id"]),
    },
    "latentcode_reject": {
        "description": "Reject a pending patch in the queue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "findings_dir": {"type": "string"},
                "patch_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["findings_dir", "patch_id"],
        },
        "handler": lambda args: tool_reject(args["findings_dir"], args["patch_id"], args.get("reason", "")),
    },
    "latentcode_apply": {
        "description": "Apply a patch from the queue to disk (writes files).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "findings_dir": {"type": "string"},
                "patch_id": {"type": "string"},
            },
            "required": ["findings_dir", "patch_id"],
        },
        "handler": lambda args: tool_apply(args["findings_dir"], args["patch_id"]),
    },
    "latentcode_queue": {
        "description": "Read the approval queue (pending + applied patches).",
        "inputSchema": {
            "type": "object",
            "properties": {"findings_dir": {"type": "string"}},
            "required": ["findings_dir"],
        },
        "handler": lambda args: tool_queue(args["findings_dir"]),
    },
    "latentcode_summary": {
        "description": "Read just the project + summary from a findings.json.",
        "inputSchema": {
            "type": "object",
            "properties": {"findings_dir": {"type": "string"}},
            "required": ["findings_dir"],
        },
        "handler": lambda args: tool_summary(args["findings_dir"]),
    },
}


def _jsonrpc_response(id, result):
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _jsonrpc_error(id, code, message):
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _handle_request(req: dict) -> dict | None:
    method = req.get("method")
    req_id = req.get("id")
    if method == "initialize":
        return _jsonrpc_response(req_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "latentcode", "version": "0.1.0"},
            "capabilities": {"tools": {}},
        })
    if method == "notifications/initialized" or method == "initialized":
        return None
    if method == "tools/list":
        return _jsonrpc_response(req_id, {
            "tools": [
                {"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
                for name, spec in TOOLS.items()
            ]
        })
    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        if name not in TOOLS:
            return _jsonrpc_error(req_id, -32601, f"unknown tool: {name}")
        try:
            result = TOOLS[name]["handler"](args)
            return _jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
                "isError": False,
            })
        except Exception as exc:
            return _jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": f"error: {exc}"}],
                "isError": True,
            })
    return _jsonrpc_error(req_id, -32601, f"unknown method: {method}")


def serve_stdio():
    """Run the MCP server over stdin/stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle_request(req)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    serve_stdio()