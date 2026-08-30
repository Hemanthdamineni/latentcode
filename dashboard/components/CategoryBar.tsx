const colors: Record<string, string> = {
  hidden_implementation: "#f59e0b",
  broken_integration: "#ef4444",
  broken_e2e_feature: "#ef4444",
  agent_shortcut: "#ef4444",
  performance: "#f59e0b",
  security: "#ef4444",
  build_dep: "#6b7280",
};

export default function CategoryBar({ byCategory }: { byCategory: Record<string, number> }) {
  const entries = Object.entries(byCategory);
  const total = entries.reduce((acc, [, n]) => acc + n, 0) || 1;
  if (entries.length === 0) {
    return <div className="text-gray-500 text-sm">No issues.</div>;
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex w-full h-3 rounded overflow-hidden border border-latent-border">
        {entries.map(([cat, n]) => (
          <div
            key={cat}
            title={`${cat}: ${n}`}
            style={{ width: `${(n / total) * 100}%`, background: colors[cat] || "#6b7280" }}
          />
        ))}
      </div>
      <div className="flex flex-col gap-1">
        {entries.map(([cat, n]) => (
          <div key={cat} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-sm" style={{ background: colors[cat] || "#6b7280" }} />
              <span className="text-gray-300">{cat}</span>
            </div>
            <span className="text-gray-500">{n}</span>
          </div>
        ))}
      </div>
    </div>
  );
}