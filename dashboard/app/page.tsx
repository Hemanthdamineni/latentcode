"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import CategoryBar from "@/components/CategoryBar";
import IssueRow from "@/components/IssueRow";

interface Findings {
  project: any;
  issues: any[];
  summary: any;
  generated_at?: string;
  static?: any;
}

export default function Page() {
  const [data, setData] = useState<Findings | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/findings`, { cache: "no-store" });
        if (!res.ok) {
          setError(`HTTP ${res.status}`);
        } else {
          setData(await res.json());
        }
      } catch (e: any) {
        setError(e?.message || String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div className="text-[13px]" style={{ color: "var(--lc-text-mute)" }}>Loading…</div>;
  }

  if (error || !data) {
    return (
      <div className="lc-card p-6">
        <div className="lc-h2 mb-2">Backend unavailable</div>
        <div className="text-[13px]" style={{ color: "var(--lc-text-dim)" }}>
          {error ? `Error: ${error}` : "No data."} Run{" "}
          <code className="lc-mono" style={{ color: "var(--lc-accent)" }}>latentcode serve</code>{" "}
          in another terminal, then refresh.
        </div>
      </div>
    );
  }

  const { issues = [], summary = {}, project } = data;
  const total = summary.total_issues ?? issues.length;
  const byCat = summary.by_category || {};
  const top = (summary.top_severity || []).slice(0, 6);
  const projectName = project?.framework === "nextjs" ? "Next.js" :
                     project?.framework === "fastapi" ? "FastAPI" :
                     project?.language || "Project";

  // The "latent" health bar: width = fill of severity-sorted issues
  const sevCounts = {
    high:   issues.filter((i) => (i.severity || 0) >= 0.7).length,
    medium: issues.filter((i) => (i.severity || 0) >= 0.4 && (i.severity || 0) < 0.7).length,
    low:    issues.filter((i) => (i.severity || 0) < 0.4).length,
  };

  return (
    <div className="lc-page">
      {/* Asymmetric: 2/3 + 1/3 split. No nested cards. */}
      <div className="grid grid-cols-[1fr_360px] gap-6">
        {/* LEFT: the headline metric + the latent health bar */}
        <div className="flex flex-col gap-6">
          <section>
            <div className="flex items-baseline gap-4">
              <div className="text-[64px] font-semibold leading-none tracking-[-0.03em] lc-mono"
                   style={{ color: "var(--lc-text)" }}>
                {total}
              </div>
              <div className="flex flex-col">
                <div className="text-[15px]" style={{ color: "var(--lc-text)" }}>
                  latent issues found
                </div>
                <div className="text-[12px]" style={{ color: "var(--lc-text-mute)" }}>
                  in {projectName} · {project?.package_manager || "—"} ·{" "}
                  {Object.keys(byCat).length} categories
                </div>
              </div>
            </div>

            {/* The latent-health bar: one segment per severity bucket, weighted */}
            <div className="mt-5 flex h-[6px] rounded-full overflow-hidden gap-px"
                 style={{ background: "var(--lc-border)" }}>
              {total > 0 && (
                <>
                  <div style={{ width: `${(sevCounts.high / total) * 100}%`, background: "var(--lc-danger)" }} />
                  <div style={{ width: `${(sevCounts.medium / total) * 100}%`, background: "var(--lc-warn)" }} />
                  <div style={{ width: `${(sevCounts.low / total) * 100}%`, background: "var(--lc-text-mute)" }} />
                </>
              )}
            </div>
            <div className="mt-2 flex items-center gap-4 text-[11px] lc-mono"
                 style={{ color: "var(--lc-text-mute)" }}>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-sm" style={{ background: "var(--lc-danger)" }} />
                {sevCounts.high} high
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-sm" style={{ background: "var(--lc-warn)" }} />
                {sevCounts.medium} medium
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-sm" style={{ background: "var(--lc-text-mute)" }} />
                {sevCounts.low} low
              </span>
            </div>
          </section>

          {/* Top issues — the table */}
          <section>
            <div className="flex items-baseline justify-between mb-3">
              <div className="lc-h2">Top issues by severity</div>
              <Link href="/findings" className="text-[12px]"
                    style={{ color: "var(--lc-accent)" }}>
                See all →
              </Link>
            </div>
            <div className="lc-card overflow-hidden">
              {top.length === 0 ? (
                <div className="px-4 py-8 text-center text-[13px]"
                     style={{ color: "var(--lc-text-mute)" }}>
                  No issues found.
                </div>
              ) : (
                top.map((i: any, idx: number) => (
                  <IssueRow key={idx} issue={i} compact />
                ))
              )}
            </div>
          </section>
        </div>

        {/* RIGHT: by-category bar + footer */}
        <div className="flex flex-col gap-6">
          <section>
            <div className="lc-h2 mb-3">By category</div>
            <div className="lc-card p-4">
              <CategoryBar byCategory={byCat} />
            </div>
          </section>

          <section>
            <div className="lc-h2 mb-3">Quick actions</div>
            <div className="flex flex-col gap-1">
              <Link href="/findings" className="lc-card px-4 py-3 flex items-center justify-between hover:opacity-90">
                <div>
                  <div className="text-[13px] font-medium" style={{ color: "var(--lc-text)" }}>Review findings</div>
                  <div className="text-[11px]" style={{ color: "var(--lc-text-mute)" }}>All {total} detected defects</div>
                </div>
                <span style={{ color: "var(--lc-text-mute)" }}>→</span>
              </Link>
              <Link href="/graph" className="lc-card px-4 py-3 flex items-center justify-between hover:opacity-90">
                <div>
                  <div className="text-[13px] font-medium" style={{ color: "var(--lc-text)" }}>View dependency graph</div>
                  <div className="text-[11px]" style={{ color: "var(--lc-text-mute)" }}>{data.static?.graph?.node_count ?? 0} nodes · {data.static?.graph?.edge_count ?? 0} edges</div>
                </div>
                <span style={{ color: "var(--lc-text-mute)" }}>→</span>
              </Link>
              <Link href="/repairs" className="lc-card px-4 py-3 flex items-center justify-between hover:opacity-90">
                <div>
                  <div className="text-[13px] font-medium" style={{ color: "var(--lc-text)" }}>Approve repair queue</div>
                  <div className="text-[11px]" style={{ color: "var(--lc-text-mute)" }}>Patches awaiting human review</div>
                </div>
                <span style={{ color: "var(--lc-text-mute)" }}>→</span>
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}