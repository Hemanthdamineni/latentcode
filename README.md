# CodeMend

> AI-powered system that finds hidden software defects — disconnected code, broken end-to-end features, agent shortcuts, optimization gaps, and security risks — then diagnoses, repairs, and measures concrete improvements.

## Problem

Modern software projects (especially those built with LLM coding agents) routinely ship code that *looks* finished but is latent:

- **Disconnected code** — components that compile but are never imported, called, or routed to
- **Broken end-to-end features** — UI exists, API exists, but the wiring between them is missing or wrong
- **Agent shortcuts** — TODO-laden stubs disguised as implementations; placeholder logic; hardcoded mocks in production paths
- **Optimization problems** — N+1 queries, missing memoization, blocking I/O in hot paths, dead algorithmic choices
- **Security risks** — leaked secrets, missing input validation, broken auth checks, dependency CVEs

Standard linters and formatters miss most of these. Tests pass because they were never written for the broken paths. The issues hide in the *gaps* between modules.

## Design Philosophy

**Tooling leads, LLMs reason.** Static analysis (tree-sitter, dependency graphs, AST) drives the discovery of *where* issues might live. LLMs judge *what* the issue means and *how* to fix it. Runtime probes verify *whether* features actually work. Three layers, each catching what the others miss.

## Interface — five ways to use it

CodeMend exposes the same pipeline through five layers so it fits any workflow:

| Layer | What it is | When to use |
|-------|------------|-------------|
| **1. CLI** | `codemend` command — `scan`, `repair`, `regress`, `fix`, `serve`, `install-hook` | Scripts, CI, terminal-first dev |
| **2. MCP server** | `codemend-mcp` — 8 tools (`codemend_scan`, `codemend_approve`, ...) | Other agents (Claude Code, Cursor, custom) |
| **3. Skill** | `skills/codemend/SKILL.md` — invoke as `/codemend` from any skills-aware agent | Conversational agent workflows |
| **4. Git hook** | `codemend install-hook` — pre-commit scan | Auto-scan on every commit |
| **5. Dashboard** | `codemend serve` + Next.js UI — review, approve, apply patches | Human-in-the-loop review |

All five layers share the same on-disk state: `<repo>/.codemend/{findings.json, approval_queue.json, findings.md}`.

### CLI quick reference

```bash
# Install
pip install -e .

# Discover
codemend scan ~/projects/myapp --judge heuristic
cat ~/projects/myapp/.codemend/findings.md

# Review via dashboard
codemend serve ~/projects/myapp/.codemend ~/projects/myapp &
cd dashboard && CODEMEND_FINDINGS=~/projects/myapp/.codemend npm run dev

# Apply (one patch)
codemend repair ~/projects/myapp/.codemend --apply <id>

# Or one-shot (no approval)
codemend fix ~/projects/myapp

# Measure impact
codemend regress ~/projects/myapp --baseline baseline.json

# Auto-scan on every commit
codemend install-hook ~/projects/myapp
# bypass: CODEMEND_SKIP=1 git commit ...
```

### MCP server

```json
// Add to ~/.config/Claude/claude_desktop_config.json or similar
{
  "mcpServers": {
    "codemend": { "command": "codemend-mcp" }
  }
}
```

Tools exposed:
- `codemend_scan(repo, phase, judge)`
- `codemend_judge(repo)`
- `codemend_regress(repo, baseline_path)`
- `codemend_queue(findings_dir)`
- `codemend_summary(findings_dir)`
- `codemend_approve(findings_dir, patch_id)`
- `codemend_reject(findings_dir, patch_id, reason)`
- `codemend_apply(findings_dir, patch_id)`

### Skill

Drop `skills/codemend/SKILL.md` into your agent's skills directory. Invoke as `/codemend scan <repo>` etc. The skill encodes the decision rules for which command to use when.

## Architecture

```
                 ┌─────────────────────────────────────────────┐
                 │        Interface Layer (5 ways in)          │
                 │  CLI  MCP  Skill  Git-hook  Dashboard       │
                 └────────────────────┬────────────────────────┘
                                      │
                                      ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                    Orchestrator (Foundry)                     │
   │  planner → architect → reviewer → debugger → validator        │
   │  + research subagents, deterministic phase gates, tracing    │
   └────────────────┬───────────────────┬─────────────────────────┘
                    │                   │
        ┌───────────▼──────────┐   ┌────▼─────────────────┐
        │   Static Analyzer    │   │   Runtime Prober     │
        │                      │   │                      │
        │ • tree-sitter AST    │   │ • spawn dev server   │
        │ • depcruise graph    │   │ • hit endpoints      │
        │ • ts-prune (unused)  │   │ • e2e probe runs     │
        │ • import resolver    │   │ • collect timings    │
        │ • route discovery    │   │ • diff before/after  │
        └──────────┬───────────┘   └────┬─────────────────┘
                   │                    │
                   ▼                    ▼
        ┌─────────────────────────────────────────┐
        │   Issue Graph (unified findings store)  │
        │   nodes: code | imports | routes | tests│
        │   edges: "calls", "imports", "routes"   │
        └─────────────────┬───────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────┐
        │   LLM Semantic Reviewer                 │
        │   guided by issue graph                 │
        │   • judge: is this a real impl or stub? │
        │   • judge: is the feature end-to-end?  │
        │   • propose: targeted patch diff       │
        │   • validate: human approval queue      │
        └─────────────────────────────────────────┘
```

## Pipeline Phases

Each project scan runs through:

1. **Specs** — discover project type (Next.js / FastAPI / Go / etc.), entry points, expected features
2. **Plan** — choose static + runtime + LLM strategies appropriate to the project
3. **Static analysis** — build dependency graph, find orphans, broken routes, unused exports
4. **Runtime probe** — boot the project, exercise routes, measure baseline metrics
5. **Semantic review** — feed findings + context to LLM reviewer, get judgment + patches
6. **Repair** — human-approved diffs applied, project re-scanned, metrics compared
7. **Done** — before/after report with concrete improvements

## Issue Taxonomy

| Category | What we find | Detection |
|---|---|---|
| **Hidden implementation** | Functions/components exist but have no callers, dead exports, unreachable branches | Static graph (entry → callee reachability) |
| **Broken integration** | Mismatched API contracts, missing env vars, unconfigured middleware | Type/schema diff + runtime probe |
| **Broken E2E feature** | UI button exists but handler is a stub; form posts to dead route | Route graph + runtime probe + LLM judge |
| **Agent shortcut** | TODO, FIXME, `pass`, placeholder returns, hardcoded mocks in prod paths | AST scan + LLM semantic review |
| **Performance** | N+1 queries, blocking sync I/O, missing memoization, oversized bundles | Static patterns + runtime timing |
| **Security** | Hardcoded secrets, missing input validation, broken auth, vulnerable deps | grep + dep audit + LLM |
| **Build/dep** | Missing scripts, broken lockfiles, dead dependencies | package.json introspection |

## Success Metrics

Measured per scan, before and after repair:

- **Build time** — `npm run build` / `tsc` / `cargo build` duration
- **Feature pass rate** — % of declared features that actually work end-to-end
- **Integration health** — % of declared external integrations that respond successfully
- **Dead code ratio** — unused exports / total exports
- **Latent issue count** — issues found by category
- **Repair success rate** — issues fixed / issues approved

## Status

Prototype. All five interface layers implemented and validated end-to-end against a synthetic Next.js target with planted defects.