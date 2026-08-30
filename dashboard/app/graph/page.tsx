import { readFindings } from "@/lib/findings";
import DepGraph from "@/components/DepGraph";

export default async function GraphPage() {
  const findings = await readFindings();
  const graph = findings?.static?.graph || { nodes: [], edges: [] };

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold">Dependency graph</h1>
        <p className="text-sm text-gray-400 mt-1">
          {graph.node_count || graph.nodes.length} nodes, {graph.edge_count || graph.edges.length} edges.
          Hover nodes to inspect, drag to rearrange.
        </p>
      </header>
      <div className="lc-card" style={{ height: 600 }}>
        <DepGraph graph={graph} />
      </div>
    </div>
  );
}