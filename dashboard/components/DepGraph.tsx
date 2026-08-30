"use client";

import { useEffect, useRef } from "react";

type Graph = {
  nodes: any[];
  edges: any[];
};

export default function DepGraph({ graph }: { graph: Graph }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const cytoscape = (await import("cytoscape")).default;
      if (cancelled || !ref.current) return;

      const elements = [
        ...graph.nodes.map((n) => ({
          data: {
            id: n.id,
            label: n.name || n.id,
            type: n.type,
            kind: n.kind,
            file: n.file,
          },
        })),
        ...graph.edges.map((e, i) => ({
          data: { id: `e${i}`, source: e.from, target: e.to, kind: e.kind },
        })),
      ];

      const cy = cytoscape({
        container: ref.current,
        elements,
        style: [
          {
            selector: "node",
            style: {
              "background-color": "#7c5cff",
              label: "data(label)",
              color: "#e5e7eb",
              "font-size": 10,
              "text-valign": "bottom",
              "text-halign": "center",
              width: 18,
              height: 18,
            },
          },
          {
            selector: 'node[type = "route"]',
            style: { "background-color": "#10b981", shape: "rectangle" },
          },
          { selector: "edge", style: { "line-color": "#1f2330", "curve-style": "bezier", width: 1 } },
          {
            selector: 'edge[kind = "imports"]',
            style: { "line-color": "#7c5cff" },
          },
          {
            selector: 'edge[kind = "routes-to"]',
            style: { "line-color": "#10b981", "target-arrow-shape": "triangle" },
          },
        ],
        layout: {
          name: "cose",
          animate: false,
          nodeRepulsion: () => 8000,
        } as any,
      });

      return () => cy.destroy();
    })();
    return () => { cancelled = true; };
  }, [graph]);

  return <div ref={ref} style={{ width: "100%", height: "100%" }} />;
}