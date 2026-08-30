import { readFindings } from "@/lib/findings";
import Stat from "@/components/Stat";
import CategoryBar from "@/components/CategoryBar";
import IssueRow from "@/components/IssueRow";

export default async function Page() {
  const findings = await readFindings();

  if (!findings) {
    return (
      <div className="lc-card">
        <h1 className="text-xl font-semibold mb-2">No findings yet</h1>
        <p className="text-gray-400 text-sm">
          Run <code className="text-latent-accent">latentcode scan &lt;repo&gt;</code> first,
          or point <code className="text-latent-accent">LATENTCODE_FINDINGS</code> at an
          existing <code>.latentcode</code> directory.
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
          <h1 className="text-2xl font-semibold">{project.framework || project.language || "Project"}</h1>
          <div className="text-sm text-gray-400 mt-1">
            {project.language} · {project.package_manager} · {issues.length} issues
          </div>
        </div>
        <div className="text-xs text-gray-500">
          generated {new Date(findings.generated_at || Date.now()).toLocaleString()}
        </div>
      </header>

      <div className="grid grid-cols-4 gap-4">
        <Stat label="Total issues" value={summary.total_issues || 0} accent="accent" />
        <Stat label="Hidden impl" value={(summary.by_category || {}).hidden_implementation || 0} accent="warn" />
        <Stat label="Agent shortcuts" value={(summary.by_category || {}).agent_shortcut || 0} accent="danger" />
        <Stat label="Broken integrations" value={(summary.by_category || {}).broken_integration || 0} accent="danger" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <section className="lc-card col-span-2">
          <h2 className="font-medium mb-3">Top issues by severity</h2>
          <div className="flex flex-col gap-2">
            {top.length === 0 && (
              <div className="text-gray-500 text-sm">No issues yet.</div>
            )}
            {top.map((i: any, idx: number) => (
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