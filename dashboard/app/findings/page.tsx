"use client";
import { useEffect, useState } from "react";
import IssueRow from "@/components/IssueRow";

interface Issue {
  category: string;
  subtype: string;
  file: string;
  line?: number;
  severity: number;
  evidence: string;
  symbol?: string;
}

export default function FindingsPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "high" | "medium" | "low">("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/findings`, { cache: "no-store" });
        if (!res.ok) setError(`HTTP ${res.status}`);
        else {
          const data = await res.json();
          setIssues(data.issues || []);
        }
      } catch (e: any) {
        setError(e?.message || String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = issues
    .filter((i) => {
      if (filter === "high" && (i.severity || 0) < 0.7) return false;
      if (filter === "medium" && !((i.severity || 0) >= 0.4 && (i.severity || 0) < 0.7)) return false;
      if (filter === "low" && (i.severity || 0) >= 0.4) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!(i.file || "").toLowerCase().includes(q) &&
            !(i.evidence || "").toLowerCase().includes(q) &&
            !(i.category || "").toLowerCase().includes(q)) return false;
      }
      return true;
    })
    .sort((a, b) => (b.severity || 0) - (a.severity || 0));

  const counts = {
    all: issues.length,
    high: issues.filter((i) => (i.severity || 0) >= 0.7).length,
    medium: issues.filter((i) => (i.severity || 0) >= 0.4 && (i.severity || 0) < 0.7).length,
    low: issues.filter((i) => (i.severity || 0) < 0.4).length,
  };

  return (
    <div className="lc-page">
      {/* Filter bar — segmented control, not a dropdown */}
      <div className="flex items-center gap-3">
        <div className="flex items-center rounded-md p-0.5"
             style={{ background: "var(--lc-surface)", border: "1px solid var(--lc-border)" }}>
          {(["all", "high", "medium", "low"] as const).map((f) => (
            <button key={f}
                    onClick={() => setFilter(f)}
                    className="px-3 py-1 text-[12px] rounded-[4px] transition-colors flex items-center gap-1.5"
                    style={{
                      background: filter === f ? "var(--lc-surface-2)" : "transparent",
                      color: filter === f ? "var(--lc-text)" : "var(--lc-text-dim)",
                      fontWeight: filter === f ? 500 : 400,
                    }}>
              <span className="capitalize">{f}</span>
              <span className="lc-mono text-[10px]"
                    style={{ color: "var(--lc-text-mute)" }}>{counts[f]}</span>
            </button>
          ))}
        </div>
        <input type="text"
               placeholder="Filter by file, category, or text…"
               value={search}
               onChange={(e) => setSearch(e.target.value)}
               className="flex-1 max-w-md px-3 py-1.5 text-[12.5px] rounded-md outline-none lc-mono"
               style={{ background: "var(--lc-surface)", border: "1px solid var(--lc-border)", color: "var(--lc-text)" }} />
        <div className="text-[12px] ml-auto" style={{ color: "var(--lc-text-mute)" }}>
          {loading ? "Loading…" :
            error ? `Error: ${error}` :
            `${filtered.length} of ${issues.length}`}
        </div>
      </div>

      {/* Findings table — no card around it, just a top-border rule */}
      <div>
        {filtered.length === 0 && !loading && !error && (
          <div className="text-center py-12 text-[13px]"
               style={{ color: "var(--lc-text-mute)" }}>
            No issues match your filter.
          </div>
        )}
        {filtered.map((i, idx) => (
          <IssueRow key={idx} issue={i} />
        ))}
      </div>
    </div>
  );
}