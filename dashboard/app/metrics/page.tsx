"use client";
import { useEffect, useState } from "react";

export default function MetricsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/findings`, { cache: "no-store" });
        if (!res.ok) setError(`HTTP ${res.status}`);
        else setData(await res.json());
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
          {error || "No data."} Start <code className="lc-mono" style={{ color: "var(--lc-accent)" }}>latentcode serve</code>.
        </div>
      </div>
    );
  }

  const issues = data.issues || [];
  const summary = data.summary || {};
  const byCat = summary.by_category || {};
  const bySubtype: Record<string, number> = {};
  for (const i of issues) {
    const k = `${i.category}::${i.subtype}`;
    bySubtype[k] = (bySubtype[k] || 0) + 1;
  }
  const subtypeList = Object.entries(bySubtype).sort((a, b) => b[1] - a[1]);

  // Aggregate health score: 100 - (weighted severity / total)
  const totalSev = issues.reduce((a: number, i: any) => a + (i.severity || 0), 0);
  const avgSev = issues.length ? totalSev / issues.length : 0;
  const health = Math.max(0, Math.round(100 - avgSev * 50));

  return (
    <div className="lc-page">
      <div className="grid grid-cols-3 gap-6">
        {/* Big number — no hero metric, just a number with a small label */}
        <div className="lc-card p-5 col-span-1">
          <div className="lc-h2 mb-3">Project health</div>
          <div className="flex items-baseline gap-2">
            <div className="text-[44px] font-semibold leading-none tracking-[-0.02em] lc-mono"
                 style={{ color: health >= 80 ? "var(--lc-ok)" :
                                  health >= 50 ? "var(--lc-warn)" : "var(--lc-danger)" }}>
              {health}
            </div>
            <div className="text-[14px] lc-mono" style={{ color: "var(--lc-text-mute)" }}>/ 100</div>
          </div>
          <div className="mt-3 text-[11.5px]" style={{ color: "var(--lc-text-dim)" }}>
            Lower severity issues reduce the score. Run <code className="lc-mono">latentcode regress</code> for a sectioned before/after report.
          </div>
        </div>

        <div className="lc-card p-5">
          <div className="lc-h2 mb-3">By category</div>
          <div className="flex flex-col gap-1.5">
            {Object.entries(byCat).sort((a, b) => b[1] - a[1]).map(([cat, n]) => {
              const total = issues.length || 1;
              return (
                <div key={cat} className="flex items-center gap-2 text-[12px]">
                  <div className="flex-1 truncate" style={{ color: "var(--lc-text-dim)" }}>{cat}</div>
                  <div className="w-24 h-1 rounded-full overflow-hidden"
                       style={{ background: "var(--lc-border)" }}>
                    <div className="h-full"
                         style={{ width: `${((n as number) / total) * 100}%`,
                                  background: "var(--lc-accent)" }} />
                  </div>
                  <div className="lc-mono w-6 text-right" style={{ color: "var(--lc-text)" }}>
                    {n as number}
                  </div>
                </div>
              );
            })}
            {Object.keys(byCat).length === 0 && (
              <div className="text-[12px] py-2" style={{ color: "var(--lc-text-mute)" }}>No issues.</div>
            )}
          </div>
        </div>

        <div className="lc-card p-5">
          <div className="lc-h2 mb-3">Summary</div>
          <dl className="text-[12.5px] flex flex-col gap-1.5">
            <div className="flex justify-between">
              <dt style={{ color: "var(--lc-text-dim)" }}>Total issues</dt>
              <dd className="lc-mono" style={{ color: "var(--lc-text)" }}>{issues.length}</dd>
            </div>
            <div className="flex justify-between">
              <dt style={{ color: "var(--lc-text-dim)" }}>Categories</dt>
              <dd className="lc-mono" style={{ color: "var(--lc-text)" }}>{Object.keys(byCat).length}</dd>
            </div>
            <div className="flex justify-between">
              <dt style={{ color: "var(--lc-text-dim)" }}>Subtypes</dt>
              <dd className="lc-mono" style={{ color: "var(--lc-text)" }}>{subtypeList.length}</dd>
            </div>
            <div className="flex justify-between">
              <dt style={{ color: "var(--lc-text-dim)" }}>Avg severity</dt>
              <dd className="lc-mono" style={{ color: "var(--lc-text)" }}>{avgSev.toFixed(2)}</dd>
            </div>
            <div className="flex justify-between">
              <dt style={{ color: "var(--lc-text-dim)" }}>Generated</dt>
              <dd className="lc-mono text-[10.5px]" style={{ color: "var(--lc-text-mute)" }}>
                {data.generated_at ? new Date(data.generated_at).toLocaleString() : "—"}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <section>
        <div className="lc-h2 mb-3">By subtype</div>
        <div className="lc-card overflow-hidden">
          {subtypeList.length === 0 ? (
            <div className="px-4 py-8 text-center text-[13px]"
                 style={{ color: "var(--lc-text-mute)" }}>No issues.</div>
          ) : (
            subtypeList.map(([key, n]) => {
              const [cat, sub] = key.split("::");
              return (
                <div key={key} className="lc-row">
                  <div className="flex-1 min-w-0 flex items-center gap-3">
                    <span className="text-[12.5px] truncate" style={{ color: "var(--lc-text)" }}>{sub}</span>
                    <span className="text-[11px] truncate" style={{ color: "var(--lc-text-mute)" }}>{cat}</span>
                  </div>
                  <div className="lc-mono text-[12px] w-8 text-right"
                       style={{ color: "var(--lc-text)" }}>{n}</div>
                </div>
              );
            })
          )}
        </div>
      </section>
    </div>
  );
}