---
name: foundry
description: "Foundry: workspace-aware autonomous SDLC runtime with phase-gated reviews, validation, debate, and cross-task memory."
trigger: /foundry
---

# Foundry: Structured Development Lifecycle Server

Foundry is an MCP server that enforces a phase-gated software development process.
It provides tools for creating tasks, transitioning through phases, evaluating
outputs, and maintaining cross-task context.

Run `sdlc-mcp` from your PATH. With no arguments it starts the Foundry MCP
server over stdio; `sdlc-mcp bootstrap` repairs the current workspace.

By default, all phase reasoning uses the model currently selected in OpenCode.
Runtime LLM providers are disabled unless `.sdlc/config/llm_config.yaml`
explicitly enables them.

## Phases

| Phase | Purpose |
|---|---|
| Chatting | Clarify task intent and scope |
| Specs | Requirements, scope, constraints |
| Planning | Implementation plan with risks |
| Coding | Write and modify code |
| Review | Code review for issues and quality |
| Testing | Run and evaluate tests |
| Done | Summarize accomplishments |

## Tools

- `sdlc_detect_workspace`: inspect execution and workspace roots
- `sdlc_bootstrap_workspace`: create or repair `.sdlc/` in the selected workspace
- `sdlc_create_task`: create a new task
- `sdlc_get_next_action`: get current phase context
- `sdlc_validate_phase`: validate phase output without mutation
- `sdlc_submit_output`: submit phase output for evaluation
- `sdlc_resume_task`: restore task state from checkpoint
- `sdlc_upgrade_workspace`: upgrade schema and generated integration files
- `sdlc_request_approval`: request or grant approval
- `sdlc_get_status`: current task status
- `sdlc_list_tasks`: list tasks filtered by status
- `sdlc_cancel_task`: cancel a task
- `sdlc_debate_output`: run multi-agent debate
- `sdlc_memory_store` / `sdlc_memory_query` / `sdlc_memory_stats`: cross-task memory
- `sdlc_index_repository` / `sdlc_index_files`: repository indexing
- `sdlc_get_dependency_context`: dependency graph for a file
- `sdlc_get_trace` / `sdlc_list_traces` / `sdlc_get_summaries`: trace inspection
- `sdlc_enforce_retention`: trace retention policy

## Usage

```
/foundry
```

Then describe what you want to build.

Call `sdlc_detect_workspace` first with no path. Inspect `execution_root`,
`workspace_root`, and `detection_reason`; if the selected workspace is not
ready, call `sdlc_bootstrap_workspace`. Do not pass parent paths or guessed
repository roots into MCP tools.
