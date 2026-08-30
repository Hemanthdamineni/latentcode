"use client";
import { useEffect, useState } from "react";
import IssueRow from "@/components/IssueRow";
import CategoryBar from "@/components/CategoryBar";

interface Issue {
  category: string;
  subtype: string;
  file: string;
  line?: number;
  severity: number;
  evidence: string;
  symbol?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_LATENTCODE_API || "http://127.0.0.1:7331";

export default function FindingsPage() {
  const [findings, setFindings] = useState<Issue[]>([]);
  const [summary, setSummary] = useState<any>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/api/findings`);
        if (res.ok) {
          const data = await res.json();
          setFindings(data.issues || []);
          setSummary(data.summary || {});
        }
      } catch {
        setFindings([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const sorted = [...findings].sort((a, b) => (b.severity || 0) - (a.severity || 0));

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold">Findings</h1>
        <p className="text-sm text-gray-400 mt-1">
          {loading ? "Loading…" : `${findings.length} issue${findings.length === 1 ? "" : "s"}, sorted by severity.`}
        </p>
      </header>

      <div className="lc-card">
        {sorted.length === 0 && !loading && (
          <div className="text-gray-500 text-sm">No issues. Run a scan first.</div>
        )}
        <div className="flex flex-col gap-2">
          {sorted.map((i, idx) => (
            <IssueRow key={idx} issue={i} detailed />
          ))}
        </div>
      </div>
    </div>
  );
}