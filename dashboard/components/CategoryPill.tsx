const labelMap: Record<string, { label: string; color: string }> = {
  hidden_implementation: { label: "Hidden impl", color: "warn" },
  broken_integration: { label: "Broken integration", color: "danger" },
  broken_e2e_feature: { label: "Broken E2E", color: "danger" },
  agent_shortcut: { label: "Agent shortcut", color: "danger" },
  performance: { label: "Performance", color: "warn" },
  security: { label: "Security", color: "danger" },
  build_dep: { label: "Build/dep", color: "muted" },
};

export default function CategoryPill({ category }: { category: string }) {
  const meta = labelMap[category] || { label: category || "unknown", color: "muted" };
  return <span className={`lc-pill lc-pill-${meta.color}`}>{meta.label}</span>;
}