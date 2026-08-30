import { readFindings } from "@/lib/findings";
import MetricCard from "@/components/MetricCard";

export default async function MetricsPage() {
  const findings = await readFindings();
  const runtime = findings?.runtime || {};
  const metrics = runtime.metrics || {};
  const summary = findings?.summary || {};

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold">Metrics</h1>
        <p className="text-sm text-gray-400 mt-1">
          Concrete measurements before/after repair. Run <code>latentcode regress</code> for
          a full sectioned report.
        </p>
      </header>

      <div className="grid grid-cols-3 gap-4">
        <MetricCard
          label="Cold start"
          value={metrics.cold_start_seconds ? `${metrics.cold_start_seconds.toFixed(2)}s` : "—"}
          hint="Time from spawn to first ready signal"
        />
        <MetricCard
          label="Endpoints working"
          value={runtime.routes_working ?? "—"}
          hint={`Out of ${runtime.endpoints?.length || 0} probed`}
        />
        <MetricCard
          label="Endpoints failing"
          value={runtime.routes_failing ?? "—"}
          hint={metrics.endpoints_4xx_5xx ? `${metrics.endpoints_4xx_5xx} returned 4xx/5xx` : ""}
        />
        <MetricCard
          label="Avg latency"
          value={metrics.latency_avg_ms ? `${metrics.latency_avg_ms}ms` : "—"}
          hint={metrics.latency_p50_ms ? `p50 ${metrics.latency_p50_ms}ms` : ""}
        />
        <MetricCard
          label="Latent issues"
          value={summary.total_issues ?? "—"}
          hint={Object.keys(summary.by_category || {}).length + " categories"}
        />
        <MetricCard
          label="Peak memory"
          value={metrics.peak_memory_mb ? `${metrics.peak_memory_mb}MB` : "—"}
          hint="Child process peak RSS"
        />
      </div>

      <section className="lc-card">
        <h2 className="font-medium mb-2">Why no "improvement %"?</h2>
        <p className="text-sm text-gray-400">
          Per the audit revision, we no longer report a composite percentage
          (fixed / total). A single number hides what actually changed. Use{" "}
          <code className="text-latent-accent">latentcode regress</code> for
          a sectioned report: feature verification, integration chains,
          latency, and static health — each with concrete before/after.
        </p>
      </section>

      {Object.keys(metrics.status_breakdown || {}).length > 0 && (
        <section className="lc-card">
          <h2 className="font-medium mb-3">Status breakdown</h2>
          <div className="flex gap-3 flex-wrap">
            {Object.entries(metrics.status_breakdown).map(([status, count]) => (
              <div key={status} className="lc-pill lc-pill-muted">
                {status}: {String(count)}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}