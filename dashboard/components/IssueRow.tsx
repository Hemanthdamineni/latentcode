import CategoryPill from "./CategoryPill";

export default function IssueRow({ issue, detailed = false }: { issue: any; detailed?: boolean }) {
  const sev = issue.severity ?? 0;
  const sevColor = sev >= 0.8 ? "danger" : sev >= 0.5 ? "warn" : "muted";
  return (
    <div className="border border-latent-border rounded-md p-3 bg-latent-bg/40 hover:bg-latent-border/30 transition">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <CategoryPill category={issue.category} />
          <span className="text-sm font-mono text-gray-300 truncate">{issue.file || "?"}:{issue.line ?? "?"}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`lc-pill lc-pill-${sevColor}`}>sev {(sev * 100).toFixed(0)}</span>
        </div>
      </div>
      <div className="text-xs text-gray-400 mt-1 truncate">{issue.evidence || ""}</div>
      {detailed && issue.snippet && (
        <pre className="text-xs bg-black/40 rounded mt-2 p-2 overflow-x-auto text-gray-300">
          {issue.snippet}
        </pre>
      )}
    </div>
  );
}