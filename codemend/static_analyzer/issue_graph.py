"""Build the unified issue graph from extracted symbols/imports/calls/routes.

The graph is a dict with `nodes` and `edges` so it's JSON-serializable
and consumable by both the LLM reviewer and the dashboard.

Also computes a `repair_scope` for each candidate by BFS through the
graph. The scope is the set of files the Proposer is allowed to touch
when fixing the candidate. Anything outside the scope requires an
explicit `--force-extra-files` flag at apply time.
"""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path


def build_issue_graph(
    repo: Path,
    symbols: list[dict],
    imports: list[dict],
    calls: list[dict],
    routes: list[str],
) -> dict:
    nodes = {}
    edges = []

    for s in symbols:
        nid = f"symbol:{s['file']}::{s['name']}"
        nodes[nid] = {
            "id": nid,
            "type": "symbol",
            "kind": s["kind"],
            "name": s["name"],
            "file": s["file"],
            "exported": s.get("exported", False),
            "line": s.get("line"),
        }

    for i in imports:
        target = i["source"]
        src_nid = f"symbol:{i['from_file']}::{i['name']}"
        for nid, node in nodes.items():
            if node["file"].endswith(target) or target.endswith(node["file"]):
                edges.append({"from": src_nid, "to": nid, "kind": "imports"})
                break

    for c in calls:
        edges.append({"from": c.get("from", ""), "to": c.get("to", ""), "kind": "calls"})

    for r in routes:
        nid = f"route:{r}"
        nodes[nid] = {"id": nid, "type": "route", "name": r, "file": None}
        handler_guess = r.replace("/", "").replace(":", "_") or "index"
        for nid2, node in nodes.items():
            if node["type"] == "symbol" and node["name"].lower() == handler_guess:
                edges.append({"from": nid, "to": nid2, "kind": "routes-to"})
                break

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def compute_repair_scope(
    graph: dict,
    candidate_file: str,
    candidate_line: int,
    max_depth: int = 3,
) -> dict:
    """BFS from the candidate through the issue graph to find fair-game files.

    Walks `imports`, `calls`, and `routes-to` edges up to `max_depth` hops.
    Returns the set of files in the scope, plus the rationale.

    A repair_scope is a *permission*, not a requirement: the Proposer may
    touch any subset. But anything outside the scope is rejected at apply
    time unless `--force-extra-files` is set.

    Args:
        graph: the issue graph from build_issue_graph
        candidate_file: file the candidate was found in
        candidate_line: line number of the candidate
        max_depth: BFS depth cap (default 3, max 5)

    Returns:
        {
            "files": ["file1", "file2", ...],
            "depth": 3,
            "rationale": "BFS from <file>:<line> through <N> hops; reached <M> files"
        }
    """
    # Build adjacency
    adj: dict[str, list[str]] = defaultdict(list)
    for e in graph.get("edges", []):
        src = e.get("from")
        tgt = e.get("to")
        if src and tgt:
            adj[src].append(tgt)
            adj[tgt].append(src)  # undirected for repair scope purposes

    # Find the seed node(s) matching the candidate
    seed_ids = []
    for node in graph.get("nodes", []):
        if node.get("file") == candidate_file:
            seed_ids.append(node["id"])
    if not seed_ids:
        # Candidate's file isn't in the graph — just the file itself
        return {
            "files": [candidate_file] if candidate_file else [],
            "depth": 0,
            "rationale": f"file '{candidate_file}' not in graph; scope is just the candidate file",
        }

    # BFS
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque((s, 0) for s in seed_ids)
    while queue:
        nid, depth = queue.popleft()
        if nid in visited or depth > max_depth:
            continue
        visited.add(nid)
        if depth < max_depth:
            for neighbor in adj.get(nid, []):
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))

    # Collect unique files from visited nodes
    files: set[str] = set()
    for nid in visited:
        for node in graph.get("nodes", []):
            if node["id"] == nid and node.get("file"):
                files.add(node["file"])
    # Always include the candidate's own file
    if candidate_file:
        files.add(candidate_file)

    return {
        "files": sorted(files),
        "depth": max_depth,
        "rationale": f"BFS from {candidate_file}:{candidate_line} through {max_depth} hops reached {len(visited)} nodes / {len(files)} files",
    }