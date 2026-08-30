"use client";
import { useEffect, useState } from "react";
import PatchCard from "@/components/PatchCard";

interface QueueItem {
  id: string;
  candidate: Record<string, any>;
  patch: string;
  patch_source: string;
}

export default function RepairsPage() {
  const [pending, setPending] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/queue`, { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          setPending(data.pending || []);
        }
      } catch {
        setPending([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold">Repair queue</h1>
        <p className="text-sm text-gray-400 mt-1">
          {loading ? "Loading…" : `${pending.length} pending patch${pending.length === 1 ? "" : "es"} for human approval.`}
        </p>
      </header>

      {pending.length === 0 && !loading && (
        <div className="lc-card text-gray-500 text-sm">
          No pending patches. Run <code className="text-latent-accent">latentcode scan --judge llm</code> to generate them.
        </div>
      )}

      <div className="grid grid-cols-1 gap-3">
        {pending.map((p) => (
          <PatchCard key={p.id} item={p} />
        ))}
      </div>
    </div>
  );
}