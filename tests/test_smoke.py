"""Smoke tests for LatentCode.

These cover the three behaviors that the v0.2 audit called out as critical:
  1. Project detection returns the right framework (sanity check for the
     whole pipeline — if detect is wrong, everything downstream is wrong)
  2. BFS repair scope computation (Challenge 1's foundation)
  3. Proposer scope validation (rejects out-of-scope patches — the
     safety boundary the audit asked for)

Run with: pytest tests/  (or python -m pytest)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the latentcode package importable when running from the repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from latentcode.project_detect import detect_project
from latentcode.static_analyzer.issue_graph import compute_repair_scope, build_issue_graph
from latentcode.llm_reviewer.proposer import propose_patches, _extract_files_from_patch


# ---------------------------------------------------------------------------
# 1. Project detection
# ---------------------------------------------------------------------------

class TestProjectDetect:
    def test_nextjs_repo_detected(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "dependencies": {"next": "14.2.0", "react": "18.3.0"},
            "scripts": {"dev": "next dev", "build": "next build"},
        }))
        spec = detect_project(tmp_path)
        assert spec.language == "javascript"
        assert spec.framework == "nextjs"
        assert spec.dev_cmd == "next dev"
        assert spec.build_cmd == "next build"

    def test_typescript_repo_detected(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "test",
            "dependencies": {"typescript": "5.0.0"},
        }))
        (tmp_path / "tsconfig.json").write_text("{}")
        spec = detect_project(tmp_path)
        assert spec.language == "typescript"

    def test_python_fastapi_detected(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\ndependencies = ['fastapi']\n")
        spec = detect_project(tmp_path)
        assert spec.language == "python"
        assert spec.framework == "fastapi"

    def test_unknown_repo(self, tmp_path):
        spec = detect_project(tmp_path)
        assert spec.language == "unknown"
        assert spec.framework == "unknown"

    def test_env_var_detection(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "test", "dependencies": {},
        }))
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "api.js").write_text(
            'const key = process.env.STRIPE_SECRET_KEY;\n'
            'const db = process.env.DATABASE_URL;\n'
        )
        spec = detect_project(tmp_path)
        assert "STRIPE_SECRET_KEY" in spec.env_vars_referenced
        assert "DATABASE_URL" in spec.env_vars_referenced


# ---------------------------------------------------------------------------
# 2. Repair scope (BFS)
# ---------------------------------------------------------------------------

class TestRepairScope:
    def _make_graph(self):
        """Build a small graph: index.js imports api.js; api.js imports util.js."""
        return {
            "node_count": 6,
            "edge_count": 4,
            "nodes": [
                {"id": "symbol:pages/index.js::Home", "type": "symbol", "kind": "component", "name": "Home", "file": "pages/index.js"},
                {"id": "symbol:lib/api.js::fetchProducts", "type": "symbol", "kind": "function", "name": "fetchProducts", "file": "lib/api.js"},
                {"id": "symbol:lib/util.js::helper", "type": "symbol", "kind": "function", "name": "helper", "file": "lib/util.js"},
                {"id": "symbol:lib/stranger.js::unrelated", "type": "symbol", "kind": "function", "name": "unrelated", "file": "lib/stranger.js"},
                {"id": "route:/api/products", "type": "route", "name": "/api/products", "file": None},
                {"id": "symbol:pages/api/products.js::handler", "type": "symbol", "kind": "function", "name": "handler", "file": "pages/api/products.js"},
            ],
            "edges": [
                {"from": "symbol:pages/index.js::Home", "to": "symbol:lib/api.js::fetchProducts", "kind": "imports"},
                {"from": "symbol:lib/api.js::fetchProducts", "to": "symbol:lib/util.js::helper", "kind": "calls"},
                {"from": "route:/api/products", "to": "symbol:pages/api/products.js::handler", "kind": "routes-to"},
            ],
        }

    def test_scope_includes_connected_files(self):
        graph = self._make_graph()
        scope = compute_repair_scope(graph, "pages/index.js", 1, max_depth=3)
        assert "pages/index.js" in scope["files"]
        assert "lib/api.js" in scope["files"]
        assert "lib/util.js" in scope["files"]

    def test_scope_excludes_unrelated_files(self):
        graph = self._make_graph()
        scope = compute_repair_scope(graph, "pages/index.js", 1, max_depth=3)
        assert "lib/stranger.js" not in scope["files"]

    def test_scope_respects_depth_cap(self):
        graph = self._make_graph()
        # depth 1: only direct neighbors
        scope_d1 = compute_repair_scope(graph, "pages/index.js", 1, max_depth=1)
        assert "pages/index.js" in scope_d1["files"]
        # util.js is 2 hops away — should NOT be in scope at depth 1
        assert "lib/util.js" not in scope_d1["files"]

    def test_scope_falls_back_gracefully_for_unknown_file(self):
        graph = self._make_graph()
        scope = compute_repair_scope(graph, "missing/file.js", 1, max_depth=3)
        assert scope["files"] == ["missing/file.js"]


# ---------------------------------------------------------------------------
# 3. Proposer scope validation (Challenge 1's safety boundary)
# ---------------------------------------------------------------------------

class TestProposerScope:
    def test_extract_files_from_patch(self):
        patch = """--- a/lib/api.js
+++ b/lib/api.js
@@ -1,1 +1,1 @@
-old
+new
--- a/lib/auth.js
+++ b/lib/auth.js
@@ -1,1 +1,1 @@
-old
+new
"""
        files = _extract_files_from_patch(patch)
        assert files == ["lib/api.js", "lib/auth.js"]

    def test_extract_files_skips_dev_null(self):
        patch = """--- a/old.js
+++ /dev/null
@@ -1,1 +0,0 @@
-gone
"""
        files = _extract_files_from_patch(patch)
        assert files == []

    def test_out_of_scope_patch_rejected(self, tmp_path):
        """The deterministic fallback should produce a patch; if its file is
        out of scope, the Proposer must reject it (empty patch + violation flag)."""
        # A scope that doesn't include the file the patch will touch.
        # The Proposer reads `repair_scope` from the verdict.
        verdict = {
            "verdict": "real",
            "classification": "stub",
            "suggested_fix_direction": "implement",
            "file": "lib/api.js",
            "line": 5,
            "repair_scope": {"files": ["lib/other.js"], "depth": 0, "rationale": "test"},
        }

        verdicts = propose_patches([verdict], tmp_path)
        v = verdicts[0]
        # The deterministic patch for "stub" modifies lib/api.js, which is
        # NOT in the scope (which has only lib/other.js), so it should be rejected.
        assert v["scope_violation"] is True
        assert v["patch"] == ""
        # The patch_summary should mention the out-of-scope file
        assert "lib/api.js" in v["patch_summary"]
        assert "rejected" in v["patch_source"]

    def test_in_scope_patch_accepted(self, tmp_path):
        """A patch that touches only in-scope files should pass through."""
        verdict = {
            "verdict": "real",
            "classification": "disconnected",
            "suggested_fix_direction": "delete",
            "file": "lib/api.js",
            "line": 1,
            "symbol": "oldThing",
            "repair_scope": {"files": ["lib/api.js"], "depth": 0, "rationale": "test"},
        }

        verdicts = propose_patches([verdict], tmp_path)
        v = verdicts[0]
        assert v["scope_violation"] is False
        assert v["patch"] != ""
        assert "lib/api.js" in v["files_modified"]

    def test_non_real_verdict_gets_no_patch(self, tmp_path):
        """False-positive and needs-info verdicts should not get patches."""
        for verdict_kind in ("false-positive", "needs-info"):
            verdict = {
                "verdict": verdict_kind,
                "classification": "stub",
                "file": "lib/api.js",
                "line": 5,
            }
            verdicts = propose_patches([verdict], tmp_path)
            v = verdicts[0]
            assert v["patch"] == ""
            assert v["patch_source"] == "n/a"


# ---------------------------------------------------------------------------
# 4. End-to-end: the synthetic target repos should produce non-zero issues
# ---------------------------------------------------------------------------

class TestTargetRepos:
    def test_broken_app_produces_issues(self):
        repo = REPO_ROOT / "examples" / "target_repos" / "broken-app"
        if not repo.exists():
            pytest.skip("broken-app example not present")
        from latentcode.project_detect import detect_project as dp
        from latentcode.static_analyzer import run_static_analysis
        spec = dp(repo)
        result = run_static_analysis(repo, spec)
        assert len(result["issues"]) > 0
        # Should find at least one of each planted category
        cats = {i["category"] for i in result["issues"]}
        assert "agent_shortcut" in cats
        assert "hidden_implementation" in cats

    def test_e2e_broken_produces_issues(self):
        repo = REPO_ROOT / "examples" / "target_repos" / "e2e-broken"
        if not repo.exists():
            pytest.skip("e2e-broken example not present")
        from latentcode.project_detect import detect_project as dp
        from latentcode.static_analyzer import run_static_analysis
        spec = dp(repo)
        result = run_static_analysis(repo, spec)
        issues = result["issues"]
        # Should catch: not_implemented stub + dead export
        subtypes = {i["subtype"] for i in issues}
        assert "not_implemented" in subtypes
        assert "dead_export" in subtypes
        # And every issue should have a repair_scope attached
        for i in issues:
            assert "repair_scope" in i, f"missing repair_scope on {i}"
            assert "files" in i["repair_scope"]
            assert "depth" in i["repair_scope"]


# ---------------------------------------------------------------------------
# 5. Eval harness produces a structured report
# ---------------------------------------------------------------------------

class TestEvalHarness:
    def test_e2e_broken_eval_runs(self):
        from latentcode.eval import run_eval
        repo = REPO_ROOT / "examples" / "target_repos" / "e2e-broken"
        if not (repo / "golden_labels.json").exists():
            pytest.skip("golden_labels.json not present")
        report = run_eval(repo)
        d = report.to_dict()
        assert "static" in d
        assert "integration" in d
        assert "behavioral" in d
        assert "overall" in d
        # On a target with planted defects, the analyzer should find them
        assert d["overall"] > 0.0
