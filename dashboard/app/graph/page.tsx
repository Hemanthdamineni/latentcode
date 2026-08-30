"use client";
import { useEffect, useState } from "react";
import DepGraph from "@/components/DepGraph";

export default function GraphPage() {
  const [graph, setGraph] = useState<{ nodes: any[]; edges: any[]; node_count?: number; edge_count?: number }>({
    nodes: [],
    edges: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/findings`, { cache: "no-store" });
        if (!res.ok) {
          setError(`HTTP ${res.status}`);
        } else {
          const data = await res.json();
          setGraph(data?.static?.graph || { nodes: [], edges: [] });
        }
      } catch (e: any) {
        setError(e?.message || String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const nodeCount = graph.node_count ?? graph.nodes.length;
  const edgeCount = graph.edge_count ?? graph.edges.length;

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dependency graph</h1>
        <p className="text-sm text-gray-400 mt-1">
          {loading
            ? "Loading…"
            : error
              ? `Backend error: ${error}`
              : `${nodeCount} nodes, ${edgeCount} edges. Hover nodes to inspect, drag to rearrange.`}
        </p>
      </header>
      <div className="lc-card" style={{ height: 600 }}>
        <DepGraph graph={graph} />
      </div>
    </div>
  );
}