# LatentCode Architecture

## Module Layout

```
LatentCode/
├── opencode.json              # Foundry agent + sdlc-mcp MCP server
├── README.md
├── ARCHITECTURE.md            # this file
├── specs/
│   ├── issue_taxonomy.yaml    # issue types, detectors, fix signals
│   └── metrics.yaml           # success metrics definitions
├── latentcode/                # Python core (orchestration + analysis)
│   ├── __init__.py
│   ├── cli.py                 # `latentcode scan <repo>` entry point
│   ├── project_detect.py      # detect Next.js / FastAPI / Go / etc.
│   ├── static_analyzer/       # tooling spine
│   │   ├── __init__.py
│   │   ├── js_analyzer.py     # tree-sitter JS/TS AST + dep graph
│   │   ├── python_analyzer.py # tree-sitter Python AST
│   │   ├── dead_export_scan.py # ts-prune / pyflakes equivalent
│   │   ├── route_discovery.py # Next.js pages/api + FastAPI routes
│   │   └── issue_graph.py     # unified findings graph
│   ├── runtime_prober/
│   │   ├── __init__.py
│   │   ├── server_lifecycle.py # spawn dev server, capture logs
│   │   ├── endpoint_probe.py   # curl each declared endpoint
│   │   ├── e2e_runner.py      # optional Playwright/headless probe
│   │   └── metrics_collector.py
│   ├── llm_reviewer/
│   │   ├── __init__.py
│   │   ├── prompts.py         # static-guided prompts
│   │   ├── judge.py           # classify + propose fix
│   │   └── patch_proposer.py  # emits unified diffs
│   ├── repair/
│   │   ├── __init__.py
│   │   ├── approval_queue.py  # human-in-the-loop gate
│   │   ├── apply_patch.py     # write diff, run validators
│   │   └── regression_check.py
│   └── report/
│       ├── __init__.py
│       └── findings.py        # JSON + Markdown reports
├── dashboard/                 # Next.js interactive UI
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx           # overview
│   │   ├── findings/page.tsx  # issue list with filters
│   │   ├── graph/page.tsx     # interactive dep graph
│   │   ├── metrics/page.tsx   # before/after charts
│   │   └── repairs/page.tsx   # approval queue
│   └── components/...
└── examples/
    └── target_repos/          # synthetic repos with planted issues
```

## Pipeline Stages

### 1. Specs — `project_detect.py`
Read package.json / pyproject / go.mod / Cargo.toml → emit `ProjectSpec`:
- language, framework, entry points, build command, dev command
- declared features (from README, file naming)
- declared integrations (env var references, third-party SDK imports)

### 2. Static Analysis — `static_analyzer/`
Run in parallel:
- **AST parse** with tree-sitter (JS/TS, Python) → symbols, imports, calls
- **Dead export scan** with `ts-prune` or hand-rolled equivalent
- **Route discovery** by framework (Next.js `pages/api`, FastAPI decorators, Express routes)
- **Pattern scan** for stubs (`TODO`, `FIXME`, `pass`, `throw NotImplementedError`, hardcoded mocks)

Output: `IssueGraph` (NetworkX graph). Nodes: files, symbols, routes, tests. Edges: `imports`, `calls`, `routes-to`, `tests`.

### 3. Reachability Analysis
From entry points (main, server, app entry, route handlers), BFS through `IssueGraph`. Anything not reached is a *candidate* hidden implementation. Not 100% accurate — feed candidates to LLM judge.

### 4. Runtime Probe — `runtime_prober/`
- Spawn dev server (detect command from ProjectSpec)
- Wait for readiness (poll health endpoint or log for "ready")
- For each declared route, record: status, response time, response shape
- For each declared integration, attempt connection (DB ping, OAuth handshake)
- Capture: cold start time, peak memory, error logs

### 5. LLM Semantic Review — `llm_reviewer/`
*Guided by* the static graph + runtime results. The prompt for each candidate includes:
- The candidate code (with file:line)
- The static evidence (e.g., "function `handleLogin` is defined but no route imports it")
- The runtime evidence (e.g., "POST /api/login returns 500")
- A rubric (is this a real impl, a stub, a feature flag, a partial?)

Outputs: classification, severity, suggested patch (unified diff).

### 6. Repair — `repair/`
Patches go into an approval queue (dashboard shows them). Each patch:
- Shows the diff + why it was proposed
- Has approve / reject / edit buttons
- On approve: applies, runs validation (lint + tests if present + cold restart)
- Re-runs the scan, computes before/after metrics

### 7. Report — `report/findings.py`
Aggregates into:
- `findings.json` — structured for dashboard
- `findings.md` — human summary
- `metrics.json` — before/after measurements

## Determinism + Validation

Foundry enforces phase gates. Each phase must:
1. Produce a structured artifact (`IssueGraph`, `ProbeReport`, etc.)
2. Pass deterministic validation (schema, sanity checks)
3. Pass LLM-as-judge for semantic tasks (judge != generator)
4. Log traces to `.sdlc/traces/`

No silent retries — failures surface immediately.

## Why Tooling Leads

LLMs are bad at *finding* candidates across thousands of files. They're good at *judging* a small set of candidates with rich context. So:

- **Tooling** does: scanning, graph building, pattern matching (deterministic, fast, cheap)
- **LLM** does: semantic judgment, root-cause reasoning, patch synthesis (slow, expensive, but smart)
- **Runtime** does: truth verification (what actually works?)

This is the same pattern Anthropic's research system uses: cheap deterministic tools to fan out, then a smart model to reason over a small set.

## LLM Reviewer Design (v0.2 — post-audit)

Per the agentic-system-design audit, the LLM reviewer is split into two personas:

```
  static + runtime evidence
           │
           ▼
    ┌─────────────────┐
    │     JUDGE       │   classifies + scores. NO patch.
    │  (judge.py)     │   emits {verdict, classification, severity,
    └────────┬────────┘           reasoning, suggested_fix_direction}
             │
             │ only `real` verdicts proceed, and only with
             │ a calculated repair_scope
             ▼
    ┌─────────────────┐
    │    PROPOSER     │   reads Judge verdict + repair_scope,
    │  (proposer.py)  │   writes the diff (single OR multi-file).
    └────────┬────────┘   emits {patch, files_modified, risks, test_suggestion}
             │
             │ diff validated against scope: any file
             │ outside repair_scope.files → patch rejected
             ▼
       Approval Queue → Human → Apply → Regress
```

**Why split?** Conflating Judge and Proposer creates self-serving bias: the
Judge who also has to write the patch is incentivized to under-report
severity so the diff stays small. Splitting eliminates the bias and makes
each role auditable independently.

**Why multi-file?** Per the v0.3 revision, the audit's "only file:line" rule
was wrong for the central use case. A broken E2E feature whose repair
crosses files (UI → API client → route handler) is LatentCode's most
important category. The Proposer may touch any file in `repair_scope`,
which is computed by BFS through the issue graph.

**Batch + shuffle**: the Judge receives up to 10 candidates per LLM call
in randomized order. This mitigates position bias (the asymmetric effect
of candidate order on LLM judgment) and reduces API latency ~10x.

**Deterministic fallback**: when `OPENAI_API_KEY` is unset, both Judge
and Proposer fall back to rule-based templates. The user still gets a
useful queue — just with template-quality patches instead of LLM-quality.

## Verification (v0.3 — post-revision)

The audit's HTTP-GET-only runtime probe was correct as a safety
boundary but insufficient as a verification story. LatentCode's central
claim is "did this feature actually work?" — which requires POST, PUT,
DELETE, and (ideally) UI interactions.

`verification_spec.yaml` is authored per project. Three safety layers:

1. **Declared only** — LatentCode will not invent endpoints or payloads.
2. **Sandboxed by default** — `isolation` block supports env_overrides,
   future DB-swap and container modes.
3. **Explicit cleanup** — even on failure, the test environment is restored.
4. **Loopback-only binding** (carried over from v0.2).

## Eval Harness (v0.3 — post-revision)

`latentcode eval` runs three classes against a target repo's
`golden_labels.json`:

- **Static** — does the analyzer find planted syntax defects (precision/recall)?
- **Integration** — does it catch UI/API/handler wiring gaps (recall only)?
- **Behavioral** — does it flag the issues that *cause* declared actions
  to fail when re-run?

The audit's single-class acceptance criterion (planted static defects
only) was circular: we built `broken-app` to satisfy the test. The
three-class harness separates what we test from what we claim.

## Future: Cross-Family Critic (v0.3, gated on golden set)

The current single-LLM design is correct for v0.1 — the 4-condition
council test scores 0/4. But if we ever add a Critic persona, it MUST
be a different model family than the Judge.

Per the [self-preference bias literature](https://arxiv.org/abs/2410.21819),
same-family judging inflates scores ~10% via self-preference. If a user
has OpenAI as their Judge, the Critic must be Anthropic (or vice versa).

**Trigger**: only build this when we have a golden set of 50+ human-labeled
candidates so we can measure whether the Critic actually improves things.
Per the rubric, we should never iterate on a judge without measurement.

## Safety Boundaries (v0.2, hardened in v0.3)

- The runtime prober refuses to spawn a server that would bind to
  non-loopback interfaces. Override with `--allow-remote`.
- Patch application returns structured errors (`PatchApplyError` with
  `rejected_hunk_line` and an actionable `hint`), not raw stderr blobs.
- The Proposer's diff is validated against the candidate's `repair_scope`;
  out-of-scope files cause the patch to be rejected (override with
  `--force-extra-files`).
- The static analyzer reads `.env*` only to detect missing keys; it
  never reads `.env.local` values and never writes to any `.env` file.
- The Proposer is explicitly forbidden from renaming files or touching
  CI/git config in its system prompt.

## Build Order

1. Project detector + static analyzer skeleton (JS/TS first)
2. Issue graph + dead export scan
3. Runtime prober (server lifecycle + endpoint probe)
4. LLM reviewer with static-guided prompts
5. Dashboard MVP (findings list + dep graph)
6. Repair queue + approval flow
7. Metrics before/after comparison
8. Example target repo with planted issues for end-to-end validation
9. Polish + docs