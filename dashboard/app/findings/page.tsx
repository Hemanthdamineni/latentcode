import { readFindings } from "@/lib/findings";
import IssueRow from "@/components/IssueRow";

export default async function FindingsPage() {
  const findings = await readFindings();
  const issues = (findings?.issues || []).slice().sort(
    (a: any, b: any) => (b.severity || 0) - (a.severity || 0)
  );

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold">Findings</h1>
        <p className="text-sm text-gray-400 mt-1">
          {issues.length} issue{issues.length === 1 ? "" : "s"}, sorted by severity.
        </p>
      </header>

      <div className="lc-card">
        {issues.length === 0 && (
          <div className="text-gray-500 text-sm">No issues. Run a scan first.</div>
        )}
        <div className="flex flex-col gap-2">
          {issues.map((i: any, idx: number) => (
            <IssueRow key={idx} issue={i} detailed />
          ))}
        </div>
      </div>
    </div>
  );
}