"use client";
import { useEffect, useState } from "react";
import MetricCard from "@/components/MetricCard";

export default function MetricsPage() {
  const [findings, setFindings] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/findings`, { cache: "no-store" });
        if (res.ok) setFindings(await res.json());
      } catch {
        setFindings(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <header>
          <h1 className="text-2xl font-semibold">Metrics</h1>
        </header>
        <p className="text-gray-500 text-sm">Loading…</p>
      </div>
    );
  }

  if (!findings) {
    return (
      <div className="flex flex-col gap-6">
        <header>
          <h1 className="text-2xl font-semibold">Metrics</h1>
        </header>
        <p className="text-sm text-gray-400 mt-1">
          Start the backend with <code>latentcode serve</code> (default port 7331), then refresh this page.
        </p>
      </div>
    );
  }

  const summary = findings.summary || {};
  const issues = findings.issues || [];

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold">Metrics</h1>
        <p className="text-sm text-gray-400 mt-1">
          Concrete measurements from the current scan. Run <code>latentcode regress</code> for a sectioned before/after report.
        </p>
      </header>

      <div className="grid grid-cols-3 gap-4">
        <MetricCard label="Total issues" value={summary.total_issues ?? 0} hint="Across all categories" />
        <MetricCard label="Dead exports" value={issues.filter((i: any) => i.subtype === "dead_export").length} hint="Unused exports" />
        <MetricCard label="Agent stubs" value={issues.filter((i: any) => i.subtype === "not_implemented" || i.subtype === "todo_comment").length} hint="TODO / not_implemented" />
        <MetricCard label="Hidden impl" value={issues.filter((i: any) => i.category === "hidden_implementation").length} hint="Unreachable code" />
        <MetricCard label="Integration" value={issues.filter((i: any) => i.category === "broken_integration").length} hint="Missing config" />
        <MetricCard label="Categories" value={Object.keys(summary.by_category || {}).length} hint="Distinct issue types" />
      </div>

      {Object.keys(summary.by_category || {}).length > 0 && (
        <section className="lc-card">
          <h2 className="font-medium mb-3">By category</h2>
          <div className="flex flex-col gap-2">
            {Object.entries(summary.by_category).map(([cat, n]) => (
              <div key={cat} className="flex items-center justify-between text-sm">
                <span className="text-gray-300 font-mono">{cat}</span>
                <span className="text-gray-400">{String(n)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}