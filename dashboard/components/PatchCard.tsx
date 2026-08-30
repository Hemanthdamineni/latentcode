"use client";

import { useState } from "react";
import CategoryPill from "./CategoryPill";
import { approvePatch, rejectPatch, applyPatch } from "@/lib/findings";

export default function PatchCard({ item }: { item: any }) {
  const [status, setStatus] = useState<"pending" | "approving" | "approved" | "applying" | "applied" | "rejecting" | "rejected" | "error">("pending");
  const [error, setError] = useState<string>("");
  const cand = item.candidate || {};

  const onApprove = async () => {
    setStatus("approving");
    try {
      await approvePatch(item.id);
      setStatus("approved");
    } catch (e: any) {
      setError(e.message);
      setStatus("error");
    }
  };

  const onApply = async () => {
    setStatus("applying");
    try {
      await approvePatch(item.id);  // mark approved first
      await applyPatch(item.id);     // then write to disk
      setStatus("applied");
    } catch (e: any) {
      setError(e.message);
      setStatus("error");
    }
  };

  const onReject = async () => {
    setStatus("rejecting");
    try {
      await rejectPatch(item.id, "");
      setStatus("rejected");
    } catch (e: any) {
      setError(e.message);
      setStatus("error");
    }
  };

  if (status === "applied") {
    return (
      <div className="lc-card">
        <div className="flex items-center gap-2">
          <div className="lc-pill lc-pill-ok">Applied to disk</div>
          <span className="text-xs text-gray-500 font-mono">[{item.id}]</span>
        </div>
        <div className="text-xs text-gray-400 mt-2">{cand.file}:{cand.line} — {cand.evidence}</div>
      </div>
    );
  }
  if (status === "approved") {
    return (
      <div className="lc-card">
        <div className="flex items-center justify-between">
          <div className="lc-pill lc-pill-ok">Approved (not yet applied)</div>
          <button
            onClick={onApply}
            className="text-xs px-3 py-1 rounded bg-latent-accent/20 text-latent-accent hover:bg-latent-accent/30"
          >
            Apply to disk
          </button>
        </div>
        <div className="text-xs text-gray-400 mt-2">{cand.file}:{cand.line} — {cand.evidence}</div>
      </div>
    );
  }
  if (status === "rejected") {
    return (
      <div className="lc-card">
        <div className="lc-pill lc-pill-muted">Rejected</div>
        <div className="text-xs text-gray-400 mt-2">{cand.file}:{cand.line} — {cand.evidence}</div>
      </div>
    );
  }

  return (
    <div className="lc-card">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <CategoryPill category={cand.category} />
          <span className="text-xs text-gray-400 font-mono">{cand.file}:{cand.line}</span>
          <span className="text-xs text-gray-500">[{item.id}]</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onApprove}
            disabled={status === "approving"}
            className="text-xs px-3 py-1 rounded bg-latent-ok/20 text-latent-ok hover:bg-latent-ok/30 disabled:opacity-50"
          >
            {status === "approving" ? "..." : "Approve"}
          </button>
          <button
            onClick={onReject}
            disabled={status === "rejecting"}
            className="text-xs px-3 py-1 rounded bg-latent-danger/20 text-latent-danger hover:bg-latent-danger/30 disabled:opacity-50"
          >
            {status === "rejecting" ? "..." : "Reject"}
          </button>
        </div>
      </div>

      {/* Repair scope (calculated from dependency graph) */}
      {cand.repair_scope && (
        <div className="mb-2">
          <div className="text-xs text-gray-500 mb-1">
            repair scope ({cand.repair_scope.files.length} file{cand.repair_scope.files.length === 1 ? "" : "s"},
            depth {cand.repair_scope.depth}):
          </div>
          <div className="flex gap-1 flex-wrap">
            {cand.repair_scope.files.map((f: string) => (
              <span key={f} className="text-xs px-2 py-0.5 rounded bg-latent-accent/15 text-latent-accent font-mono">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Files this patch actually touches */}
      {cand.files_modified && cand.files_modified.length > 0 && (
        <div className="mb-2">
          <div className="text-xs text-gray-500 mb-1">patch modifies:</div>
          <div className="flex gap-1 flex-wrap">
            {cand.files_modified.map((f: string) => (
              <span key={f} className="text-xs px-2 py-0.5 rounded bg-latent-ok/15 text-latent-ok font-mono">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="text-sm text-gray-300 mb-2">{cand.evidence}</div>
      {item.patch && (
        <pre className="text-xs bg-black/40 rounded p-2 overflow-x-auto text-gray-300 max-h-48">
          {item.patch}
        </pre>
      )}
      {cand.risks && (
        <div className="text-xs text-latent-warn mt-2">⚠ {cand.risks}</div>
      )}
      {cand.test_suggestion && (
        <div className="text-xs text-gray-500 mt-1">verify: {cand.test_suggestion}</div>
      )}
      <div className="text-xs text-gray-500 mt-2">patch source: {item.patch_source}</div>
      {status === "error" && <div className="text-xs text-latent-danger mt-2">{error}</div>}
    </div>
  );
}