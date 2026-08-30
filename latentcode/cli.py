"""LatentCode CLI.

Usage:
    latentcode scan <repo> [--phase static|runtime|all] [--out DIR] [--judge heuristic|llm]
    latentcode repair <findings_dir> [--apply ID]
    latentcode regress <repo> [--baseline findings.json]
    latentcode serve <findings_dir> <repo_root> [--port 7331]
    latentcode fix <repo>                # one-shot: scan + judge + apply all
    latentcode install-hook <repo>       # install pre-commit git hook
    latentcode verify <repo>             # run verification_spec.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .project_detect import detect_project
from .static_analyzer import run_static_analysis
from .runtime_prober import run_runtime_probe
from .llm_reviewer import review_candidates, propose_patches
from .report.findings import write_findings
from .repair import ApprovalQueue, apply_patch, run_regression_check


def cmd_scan(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    if not repo.exists():
        print(f"error: {repo} does not exist", file=sys.stderr)
        return 1

    print(f"→ Detecting project type for {repo}")
    spec = detect_project(repo)
    print(f"  language: {spec.language}  framework: {spec.framework}")
    if spec.entry_points:
        print(f"  entry points: {', '.join(spec.entry_points[:3])}")
    if spec.build_cmd:
        print(f"  build cmd: {spec.build_cmd}")
    if spec.dev_cmd:
        print(f"  dev cmd: {spec.dev_cmd}")
    if spec.declared_features:
        print(f"  declared features: {len(spec.declared_features)}")

    findings = {"project": spec.to_dict(), "phases": {}}

    if args.phase in ("static", "all"):
        print("→ Running static analysis")
        scope_depth = min(max(getattr(args, "max_scope_depth", 3), 1), 5)
        static_result = run_static_analysis(repo, spec, max_scope_depth=scope_depth)
        findings["phases"]["static"] = static_result
        issues = static_result.get("issues", [])
        print(f"  findings: {len(issues)}")
        by_cat = {}
        for i in issues:
            by_cat[i.get("category", "?")] = by_cat.get(i.get("category", "?"), 0) + 1
        for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {n}")

    if args.phase in ("runtime", "all"):
        print("→ Running runtime probe")
        runtime_result = run_runtime_probe(repo, spec, allow_remote=getattr(args, "allow_remote", False))
        findings["phases"]["runtime"] = runtime_result
        if runtime_result.get("skipped"):
            print("  skipped: no dev_cmd detected")
        else:
            print(f"  endpoints probed: {len(runtime_result.get('endpoints', []))}")
            print(f"  working: {runtime_result.get('routes_working', 0)}  failing: {runtime_result.get('routes_failing', 0)}")

    if args.judge and findings["phases"].get("static", {}).get("issues"):
        print(f"→ Reviewing candidates with {args.judge} judge")
        static = findings["phases"]["static"]
        candidates = [
            {**issue, "id": f"{issue.get('file', '?')}::{issue.get('line', 0)}::{issue.get('subtype', '?')}"}
            for issue in static["issues"]
        ]
        # Step 1: Judge classifies + scores
        verdicts = review_candidates(candidates, repo, provider=args.judge, shuffle=True)
        # Step 2: Proposer writes patches for `real` verdicts only
        verdicts = propose_patches(verdicts, repo)
        findings["phases"]["review"] = {"verdicts": verdicts}

        # Queue real-verdict patches
        if not args.no_queue:
            queue = ApprovalQueue(repo / ".latentcode" / "approval_queue.json")
            # Judge shuffles, so pair by candidate_id, not by position
            by_id = {v.get("candidate_id"): v for v in verdicts}
            queued = 0
            for cand in candidates:
                v = by_id.get(cand.get("id"))
                if not v or v.get("verdict") != "real" or not v.get("patch"):
                    continue
                rich_candidate = {
                    **cand,
                    "verdict": v.get("verdict"),
                    "classification": v.get("classification"),
                    "severity": v.get("severity"),
                    "reasoning": v.get("reasoning"),
                    "suggested_fix_direction": v.get("suggested_fix_direction"),
                    "risks": v.get("risks"),
                    "test_suggestion": v.get("test_suggestion"),
                    "repair_scope": v.get("repair_scope"),
                    "files_modified": v.get("files_modified", []),
                }
                queue.add(rich_candidate, v["patch"], source=v.get("patch_source", "unknown"))
                queued += 1
            print(f"  queued {queued} patches for approval")

    out_dir = Path(args.out) if hasattr(args, "out") and args.out else repo / ".latentcode"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_findings(findings, out_dir)
    print(f"✓ Wrote findings to {out_dir}")
    return 0


def cmd_repair(args: argparse.Namespace) -> int:
    queue_path = Path(args.findings_dir) / "approval_queue.json"
    if not queue_path.exists():
        print(f"error: no approval queue at {queue_path}", file=sys.stderr)
        return 1
    queue = ApprovalQueue(queue_path)
    pending = queue.list_pending()
    if not pending:
        print("No pending patches.")
        return 0
    target = args.apply
    if target:
        item = next((p for p in pending if p["id"] == target), None)
        if not item:
            print(f"No patch with id {target}", file=sys.stderr)
            return 1
        results = apply_patch(item["patch"], Path(args.findings_dir).parent, dry_run=args.dry_run)
        print(f"Patch {target}: {results}")
        if not args.dry_run:
            queue.approve(target)
    else:
        print(f"{len(pending)} pending patch(es). Use --apply <id> to apply.")
        for p in pending[:10]:
            cand = p.get("candidate", {})
            print(f"  [{p['id']}] {cand.get('category', '?')}: {cand.get('evidence', '')[:80]}")
    return 0


def cmd_regress(args: argparse.Namespace) -> int:
    from .repair.regression_check import run_regression_check, render_markdown
    repo = Path(args.repo).resolve()
    pre_path = Path(args.baseline) if args.baseline else repo / ".latentcode" / "findings.json"
    if not pre_path.exists():
        print(f"error: no baseline findings at {pre_path}", file=sys.stderr)
        return 1
    pre = json.loads(pre_path.read_text(encoding="utf-8"))

    # Also load pre + post verification results if they exist
    findings_dir = pre_path.parent
    pre_ver = None
    pre_ver_path = findings_dir / "verification_results.json"
    if pre_ver_path.exists():
        try:
            pre_ver = json.loads(pre_ver_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pre_ver = None
    post_ver = None
    post_ver_path = repo / ".latentcode" / "verification_results.json"
    if post_ver_path.exists():
        try:
            post_ver = json.loads(post_ver_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            post_ver = None

    spec = detect_project(repo)
    result = run_regression_check(repo, spec, pre, pre_verification=pre_ver, post_verification=post_ver)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(render_markdown(result))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .serve import serve
    serve(Path(args.findings_dir), Path(args.repo), host=args.host, port=args.port)
    return 0


def cmd_fix(args: argparse.Namespace) -> int:
    """One-shot: scan + judge + apply all real patches + regress check.

    For trusted workflows. No human-in-the-loop.
    """
    repo = Path(args.repo).resolve()
    spec = detect_project(repo)
    scope_depth = min(max(getattr(args, "max_scope_depth", 3), 1), 5)
    static = run_static_analysis(repo, spec, max_scope_depth=scope_depth)
    runtime = run_runtime_probe(repo, spec)
    findings = {"project": spec.to_dict(), "phases": {"static": static, "runtime": runtime}}
    write_findings(findings, repo / ".latentcode")

    candidates = [{**i, "id": f"{i.get('file', '?')}::{i.get('line', 0)}::{i.get('subtype', '?')}"}
                  for i in static.get("issues", [])]
    verdicts = review_candidates(candidates, repo, provider=args.judge, shuffle=True)
    verdicts = propose_patches(verdicts, repo)
    applied = 0
    queue = ApprovalQueue(repo / ".latentcode" / "approval_queue.json")
    # Judge shuffles; pair by candidate_id
    by_id = {v.get("candidate_id"): v for v in verdicts}
    for cand in candidates:
        v = by_id.get(cand.get("id"))
        if not v or v.get("verdict") != "real" or not v.get("patch"):
            continue
        results = apply_patch(v["patch"], repo, dry_run=False)
        if results and results[0].get("applied"):
            applied += 1
            rich = {**cand, "files_modified": v.get("files_modified", []), "repair_scope": v.get("repair_scope")}
            queue.add(rich, v["patch"], source=v.get("patch_source", "unknown"))
            queue.approve(queue.list_pending()[-1]["id"])
    print(f"Applied {applied} of {len(candidates)} patches")
    return 0


def cmd_install_hook(args: argparse.Namespace) -> int:
    """Install a pre-commit git hook that runs `latentcode scan`."""
    repo = Path(args.repo).resolve()
    git_dir = repo / ".git"
    if not git_dir.exists():
        print(f"error: {repo} is not a git repo", file=sys.stderr)
        return 1
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_path = hooks_dir / "pre-commit"
    hook_content = """#!/usr/bin/env bash
# LatentCode pre-commit hook — scans the staged changes for latent issues.
# Set LATENTCODE_SKIP=1 to bypass.
set -e
[ -n "$LATENTCODE_SKIP" ] && exit 0
if ! command -v latentcode >/dev/null 2>&1; then
  echo "latentcode: command not found, skipping scan" >&2
  exit 0
fi
echo "→ LatentCode: scanning staged changes"
latentcode scan . --phase static --judge heuristic --no-queue
"""
    hook_path.write_text(hook_content, encoding="utf-8")
    hook_path.chmod(0o755)
    print(f"✓ Installed pre-commit hook at {hook_path}")
    print("  bypass with: LATENTCODE_SKIP=1 git commit ...")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="latentcode")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="scan a repo for latent issues")
    p_scan.add_argument("repo", help="path to repo to scan")
    p_scan.add_argument("--phase", choices=["static", "runtime", "all"], default="all")
    p_scan.add_argument("--out", default=None, help="output directory")
    p_scan.add_argument("--judge", default=None, choices=["heuristic", "llm", "auto"],
                        help="run LLM-style review on candidates")
    p_scan.add_argument("--no-queue", action="store_true", help="don't queue patches")
    p_scan.add_argument("--allow-remote", action="store_true",
                        help="allow the runtime prober to bind to non-loopback interfaces (off by default)")
    p_scan.add_argument("--max-scope-depth", type=int, default=3,
                        help="BFS depth cap for computing each candidate's repair scope (default 3, max 5)")
    p_scan.set_defaults(func=cmd_scan)

    p_repair = sub.add_parser("repair", help="review and apply queued patches")
    p_repair.add_argument("findings_dir", help=".latentcode directory")
    p_repair.add_argument("--apply", help="patch id to apply")
    p_repair.add_argument("--dry-run", action="store_true", default=True)
    p_repair.add_argument("--commit", action="store_true", help="actually write the patch")
    p_repair.set_defaults(func=cmd_repair)

    p_regress = sub.add_parser("regress", help="re-run scan and compare to prior findings")
    p_regress.add_argument("repo", help="path to repo")
    p_regress.add_argument("--baseline", default=None,
                            help="path to baseline findings.json (default: <repo>/.latentcode/findings.json)")
    p_regress.add_argument("--json", action="store_true", help="emit raw JSON instead of Markdown")
    p_regress.set_defaults(func=cmd_regress)

    p_serve = sub.add_parser("serve", help="start the dashboard backend (HTTP API)")
    p_serve.add_argument("findings_dir", help=".latentcode directory")
    p_serve.add_argument("repo", help="repo root (for /api/apply and /api/rescan)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=7331)
    p_serve.set_defaults(func=cmd_serve)

    p_fix = sub.add_parser("fix", help="one-shot: scan + judge + apply all real patches")
    p_fix.add_argument("repo", help="path to repo")
    p_fix.add_argument("--judge", default="heuristic", choices=["heuristic", "llm", "auto"])
    p_fix.set_defaults(func=cmd_fix)

    p_hook = sub.add_parser("install-hook", help="install a pre-commit git hook")
    p_hook.add_argument("repo", help="path to git repo")
    p_hook.set_defaults(func=cmd_install_hook)

    p_verify = sub.add_parser("verify", help="run a verification_spec.yaml against a live project")
    p_verify.add_argument("repo", help="path to repo with .latentcode/verification_spec.yaml")
    p_verify.add_argument("--spec", default=None, help="path to verification_spec.yaml (default: <repo>/.latentcode/verification_spec.yaml)")
    p_verify.add_argument("--base-url", default="http://127.0.0.1:3000", help="base URL of the running app")
    p_verify.add_argument("--continue-on-failure", action="store_true", help="don't stop on the first failed action")
    p_verify.set_defaults(func=cmd_verify)

    p_eval = sub.add_parser("eval", help="run the three-class eval harness against a target repo")
    p_eval.add_argument("repo", help="path to target repo with golden_labels.json")
    p_eval.add_argument("--json", action="store_true", help="emit raw JSON")
    p_eval.set_defaults(func=cmd_eval)

    args = parser.parse_args()
    return args.func(args)


def cmd_verify(args: argparse.Namespace) -> int:
    from .verification import load_spec, run_verification
    repo = Path(args.repo).resolve()
    spec_path = Path(args.spec) if args.spec else repo / ".latentcode" / "verification_spec.yaml"
    if not spec_path.exists():
        print(f"error: verification_spec not found at {spec_path}", file=sys.stderr)
        print("create one at <repo>/.latentcode/verification_spec.yaml", file=sys.stderr)
        return 1
    spec = load_spec(spec_path)
    print(f"→ Running {len(spec.actions)} action(s) from {spec_path}")
    result = run_verification(spec, base_url=args.base_url, stop_on_failure=not args.continue_on_failure)
    out_path = repo / ".latentcode" / "verification_results.json"
    out_path.write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
    print()
    for a in result.action_results:
        marker = "✓" if a.passed else "✗"
        print(f"  {marker} {a.name} ({a.duration_ms:.0f}ms)")
        if a.error:
            print(f"      {a.error}")
    print()
    print(f"Passed: {result.actions_passed}/{result.actions_total}")
    print(f"Wrote: {out_path}")
    return 0 if result.actions_passed == result.actions_total else 1


def cmd_eval(args: argparse.Namespace) -> int:
    from .eval import run_eval
    repo = Path(args.repo).resolve()
    if not (repo / "golden_labels.json").exists():
        print(f"error: no golden_labels.json at {repo}", file=sys.stderr)
        return 1
    report = run_eval(repo)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(report.render_markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main())