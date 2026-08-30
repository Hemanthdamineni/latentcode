# LatentCode Dashboard

Interactive UI for LatentCode findings, dep graph, metrics, and repair queue.

## Run

```bash
# 1. Run a scan against a repo (writes .latentcode/ inside it)
latentcode scan /path/to/repo --judge heuristic

# 2. Point the dashboard at the findings
cd dashboard
LATENTCODE_FINDINGS=/path/to/repo/.latentcode npm run dev
```

The dashboard reads `findings.json` and `approval_queue.json` from
`LATENTCODE_FINDINGS` (defaults to `./.latentcode`).

## Pages

- **Overview** — headline stats + top issues + category breakdown
- **Findings** — full sortable list, with snippets and severity
- **Dependency graph** — interactive Cytoscape graph of files/symbols/routes
- **Metrics** — cold start, latency, working/failing endpoints, peak memory
- **Repair queue** — approve/reject pending patches (preview UI; the real
  apply command is `latentcode repair` from the CLI)

## Stack

- Next.js 14 (app router)
- TailwindCSS (dark theme tuned for terminal aesthetic)
- Cytoscape.js (dep graph)
- Recharts (metric trends — add when you have time-series data)