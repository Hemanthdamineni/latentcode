# CodeMend Dashboard

Interactive UI for CodeMend findings, dep graph, metrics, and repair queue.

## Run

```bash
# 1. Run a scan against a repo (writes .codemend/ inside it)
codemend scan /path/to/repo --judge heuristic

# 2. Point the dashboard at the findings
cd dashboard
CODEMEND_FINDINGS=/path/to/repo/.codemend npm run dev
```

The dashboard reads `findings.json` and `approval_queue.json` from
`CODEMEND_FINDINGS` (defaults to `./.codemend`).

## Pages

- **Overview** — headline stats + top issues + category breakdown
- **Findings** — full sortable list, with snippets and severity
- **Dependency graph** — interactive Cytoscape graph of files/symbols/routes
- **Metrics** — cold start, latency, working/failing endpoints, peak memory
- **Repair queue** — approve/reject pending patches (preview UI; the real
  apply command is `codemend repair` from the CLI)

## Stack

- Next.js 14 (app router)
- TailwindCSS (dark theme tuned for terminal aesthetic)
- Cytoscape.js (dep graph)
- Recharts (metric trends — add when you have time-series data)