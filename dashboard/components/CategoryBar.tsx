"use client";

const CATEGORY_COLORS: Record<string, string> = {
  hidden_implementation:  "var(--lc-accent)",
  broken_integration:     "var(--lc-danger)",
  broken_e2e_feature:      "var(--lc-danger)",
  agent_shortcut:         "var(--lc-warn)",
  performance:            "var(--lc-warn)",
  security:               "var(--lc-danger)",
  build_dep:              "var(--lc-text-mute)",
};

const CATEGORY_LABELS: Record<string, string> = {
  hidden_implementation:  "hidden impl",
  broken_integration:     "broken integration",
  broken_e2e_feature:      "broken E2E",
  agent_shortcut:         "agent shortcut",
  performance:            "performance",
  security:               "security",
  build_dep:              "build / dep",
};

export default function CategoryBar({ byCategory }: { byCategory: Record<string, number> }) {
  const entries = Object.entries(byCategory);
  const total = entries.reduce((a, [, n]) => a + n, 0) || 1;

  if (entries.length === 0) {
    return (
      <div className="text-[12px] text-center py-4"
           style={{ color: "var(--lc-text-mute)" }}>
        No issues to categorize.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Stacked horizontal bar */}
      <div className="flex h-[6px] rounded-full overflow-hidden gap-px"
           style={{ background: "var(--lc-border)" }}>
        {entries.map(([cat, n]) => (
          <div key={cat}
               title={`${CATEGORY_LABELS[cat] || cat}: ${n}`}
               style={{
                 width: `${(n / total) * 100}%`,
                 background: CATEGORY_COLORS[cat] || "var(--lc-text-mute)",
               }} />
        ))}
      </div>

      {/* Legend — only the categories that exist, with their count + percentage */}
      <div className="flex flex-col gap-1.5">
        {entries
          .sort((a, b) => b[1] - a[1])
          .map(([cat, n]) => (
            <div key={cat} className="flex items-center justify-between text-[12px]">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-sm shrink-0"
                      style={{ background: CATEGORY_COLORS[cat] || "var(--lc-text-mute)" }} />
                <span style={{ color: "var(--lc-text-dim)" }}>{CATEGORY_LABELS[cat] || cat}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="lc-mono" style={{ color: "var(--lc-text)" }}>{n}</span>
                <span className="lc-mono text-[10px] w-8 text-right"
                      style={{ color: "var(--lc-text-mute)" }}>
                  {Math.round((n / total) * 100)}%
                </span>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}