"use client";
import { useEffect, useState } from "react";
import Stat from "@/components/Stat";
import CategoryBar from "@/components/CategoryBar";
import IssueRow from "@/components/IssueRow";

const API_BASE = process.env.NEXT_PUBLIC_LATENTCODE_API || "http://127.0.0.1:7331";

export default function Page() {
  const [findings, setFindings] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/findings`);
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
      <div className="lc-card">
        <h1 className="text-xl font-semibold mb-2">LatentCode</h1>
        <p className="text-gray-400 text-sm">Loading findings from {API_BASE}…</p>
      </div>
    );
  }

  if (!findings) {
    return (
      <div className="lc-card">
        <h1 className="text-xl font-semibold mb-2">No findings yet</h1>
        <p className="text-gray-400 text-sm">
          Start the backend with <code className="text-latent-accent">latentcode serve</code> (default port 7331), then refresh this page.
        </p>
      </div>
    );
  }

  const summary = findings.summary || {};
  const project = findings.project || {};
  const issues = findings.issues || [];
  const top = (summary.top_severity || []).slice(0, 5);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{(findings.project && (findings.project.framework || findings.project.language)) || "Project"}</h1>
          <div className="text-sm text-gray-400 mt-1">
            {findings.project?.language || ""} · {findings.project?.package_manager || ""} · {summary.total_issues ?? 0} issues
          </div>
        </div>
        <div className="text-xs text-gray-500">
          loaded {new Date(findings.generated_at || Date.now()).toLocaleString()}
        </div>
      </header>

      <div className="grid grid-cols-4 gap-4">
        <Stat label="Total issues" value={summary.total_issues || 0} accent="accent" />
        <Stat label="Hidden impl" value={(summary.by_category || {}).hidden_implementation || 0} accent="warn" />
        <Stat label="Agent stubs" value={(summary.by_category || {}).agent_shortcut || 0} accent="danger" />
        <Stat label="Broken integrations" value={(summary.by_category || {}).broken_integration || 0} accent="danger" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <section className="lc-card col-span-2">
          <h2 className="font-medium mb-3">Top issues by severity</h2>
          <div className="flex flex-col gap-2">
            {(summary.top_severity || []).length === 0 && (
              <div className="text-gray-500 text-sm">No issues yet.</div>
            )}
            {(summary.top_severity || []).map((i: any, idx: number) => (
              <IssueRow key={idx} issue={i} />
            ))}
          </div>
        </section>
        <section className="lc-card">
          <h2 className="font-medium mb-3">By category</h2>
          <CategoryBar byCategory={summary.by_category || {}} />
        </section>
      </div>
    </div>
  );
}