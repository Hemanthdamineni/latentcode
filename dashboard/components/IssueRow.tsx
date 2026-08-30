"use client";

const CATEGORY_COLORS: Record<string, string> = {
  hidden_implementation:  "lc-pill-amber",
  broken_integration:     "lc-pill-red",
  broken_e2e_feature:      "lc-pill-red",
  agent_shortcut:         "lc-pill-warn",
  performance:            "lc-pill-warn",
  security:               "lc-pill-red",
  build_dep:              "lc-pill-mute",
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

export default function IssueRow({ issue, compact = false }: { issue: any; compact?: boolean }) {
  const sev = issue.severity ?? 0;
  const cat = issue.category || "unknown";
  const catClass = CATEGORY_COLORS[cat] || "lc-pill-mute";
  const catLabel = CATEGORY_LABELS[cat] || cat;
  const file = issue.file || "—";
  const line = issue.line ?? "—";

  // The "latent-ness" indicator: amber when fresh/active, gray when stale.
  // We use the issue's severity to drive intensity.
  const dormClass = sev >= 0.7 ? "fresh" : sev >= 0.4 ? "" : "stale";

  if (compact) {
    return (
      <div className="lc-row gap-3">
        <div className={`lc-dormant ${dormClass} shrink-0`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-[13px]">
            <span className="lc-pill" style={{ background: "var(--lc-bg)" }}>
              <span className={`inline-block w-1.5 h-1.5 rounded-full`}
                    style={{ background: sev >= 0.7 ? "var(--lc-danger)" :
                                     sev >= 0.4 ? "var(--lc-warn)" : "var(--lc-text-mute)" }} />
              {sev.toFixed(2)}
            </span>
            <span className={`lc-pill ${catClass}`}>{catLabel}</span>
            <span className="lc-mono truncate" style={{ color: "var(--lc-text)" }}>
              {file}:{line}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="lc-row items-start gap-3 py-3.5">
      <div className={`lc-dormant ${dormClass} mt-1.5 shrink-0`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={`lc-pill ${catClass}`}>{catLabel}</span>
          <span className="lc-mono text-[12.5px] truncate" style={{ color: "var(--lc-text)" }}>
            {file}:{line}
          </span>
          <span className="ml-auto lc-mono text-[11px]"
                style={{ color: sev >= 0.7 ? "var(--lc-danger)" :
                                 sev >= 0.4 ? "var(--lc-warn)" : "var(--lc-text-mute)" }}>
            sev {sev.toFixed(2)}
          </span>
        </div>
        <div className="text-[12.5px] leading-relaxed"
             style={{ color: "var(--lc-text-dim)" }}>
          {issue.evidence || "—"}
        </div>
      </div>
    </div>
  );
}