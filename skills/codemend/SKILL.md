---
name: codemend
description: CodeMend is a hidden-defect analyzer. Use when the user asks to find, fix, or measure latent issues, dead code, agent stubs, broken E2E features, disconnected components, or wants a defect report. Triggers include "find latent issues", "audit my code", "what's broken", "scan for stubs", "diagnose this project", "repair queue".
allowed-tools:
  - Bash(codemend *)
  - Bash(codemend-mcp *)
  - Read
  - Edit
  - Write
---

# CodeMend

A tool-led analysis system that finds hidden defects in software projects
(disconnected code, broken end-to-end features, agent shortcuts, missing
env vars, dead exports), proposes minimal patches, and measures concrete
before/after improvements.

## When to use this skill

Activate when the user asks to:
- **Find latent issues** in a project ("what's broken?", "audit this code")
- **Diagnose** a failing feature ("why doesn't this work end-to-end?")
- **Measure** the impact of a repair ("how much did this fix improve things?")
- **Triage** an agent-generated codebase
- **Repair** known issues ("fix all the broken stubs")

Don't use for: syntax errors, lint, formatting, simple Q&A about code.

## Quick workflow

```bash
# 1. Discover
codemend scan <repo> --judge heuristic
# → writes .codemend/findings.json + .codemend/approval_queue.json

# 2. Inspect
cat <repo>/.codemend/findings.md
# or browse the dashboard:
codemend serve <repo>/.codemend <repo> &
cd dashboard && CODEMEND_FINDINGS=<repo>/.codemend npm run dev

# 3. Repair (after human approval)
codemend repair <repo>/.codemend --apply <id>
# or
codemend fix <repo>  # one-shot, no approval

# 4. Measure
codemend regress <repo> --baseline baseline.json
# → { fixed_count, new_count, improvement_pct }
```

## Decision rules

| User intent | Command |
|-------------|---------|
| "scan / audit / find issues" | `codemend scan <repo> --judge heuristic` |
| "show me the dashboard" | `codemend serve <dir> <repo> &` + dashboard dev |
| "fix all of it" | `codemend fix <repo>` (no approval) |
| "fix this specific one" | `codemend repair <dir> --apply <id>` |
| "did my fix work?" | `codemend regress <repo> --baseline before.json` |
| "set up auto-scan on commit" | `codemend install-hook <repo>` |
| "let me drive it as tools" | register `codemend-mcp` as an MCP server |

## Output shapes

### `findings.json`
```json
{
  "project": { "language": "...", "framework": "...", "entry_points": [...] },
  "static": { "stats": {...}, "graph": {...}, "routes": [...] },
  "runtime": { "endpoints": [...], "metrics": {...} },
  "issues": [
    { "category": "agent_shortcut", "subtype": "not_implemented",
      "file": "...", "line": 7, "severity": 0.8, "evidence": "..." }
  ],
  "summary": { "total_issues": N, "by_category": {...}, "top_severity": [...] }
}
```

### Issue categories
- `hidden_implementation` — exported but unused, unreachable
- `agent_shortcut` — `TODO`, `not_implemented`, hardcoded mocks
- `broken_integration` — missing env vars, mismatched contracts
- `broken_e2e_feature` — wiring gaps between UI/API/handler
- `performance` — N+1, blocking I/O, missing memoization
- `security` — secrets, missing validation, broken auth
- `build_dep` — missing scripts, dead deps, lockfile issues

## Hard rules

- **Always run `codemend scan` first** before any repair action.
- **Always run `codemend regress` after a repair** to measure impact.
- **Never auto-apply patches** without the user explicitly saying
  "fix", "repair", "apply", or "go".
- **Default to heuristic judge** unless the user has an OpenAI key
  configured (set `OPENAI_API_KEY` and use `--judge llm`).
- **Dashboard is for review**, not autopilot. When the user wants to
  see and decide, point them at the dashboard. When they want results,
  run the CLI.

## MCP integration

CodeMend is also available as MCP tools. Add to your MCP config:

```json
{
  "mcpServers": {
    "codemend": {
      "command": "codemend-mcp"
    }
  }
}
```

Tools: `codemend_scan`, `codemend_judge`, `codemend_regress`,
`codemend_approve`, `codemend_reject`, `codemend_apply`,
`codemend_queue`, `codemend_summary`.

## Common patterns

### Audit then report
```bash
codemend scan <repo> --judge heuristic
# Read the markdown summary, surface the top 3-5 issues to the user
```

### Repair with measurement
```bash
# Baseline
codemend scan <repo> --judge heuristic --out /tmp/baseline
# Apply
codemend fix <repo> --judge heuristic
# Measure
codemend regress <repo> --baseline /tmp/baseline/findings.json
# Report: fixed X, new Y, improvement Z%
```

### Drive from another agent
Use the MCP tools. `codemend_scan` → `codemend_summary` →
`codemend_queue` → loop `codemend_approve` / `codemend_reject` →
`codemend_apply` → `codemend_regress`.

## Philosophy

CodeMend is **tooling-led, LLM-assisted**. Static analysis builds the
candidate set; the LLM judges semantic intent; runtime probes verify
truth. Three layers, each catching what the others miss. The skill
exists to make this orchestration obvious to any agent.
