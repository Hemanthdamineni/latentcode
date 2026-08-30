import { readQueue } from "@/lib/findings";
import PatchCard from "@/components/PatchCard";

export default async function RepairsPage() {
  const pending = await readQueue();
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold">Repair queue</h1>
        <p className="text-sm text-gray-400 mt-1">
          {pending.length} pending patch{pending.length === 1 ? "" : "es"} for human approval.
        </p>
      </header>

      {pending.length === 0 && (
        <div className="lc-card text-gray-500 text-sm">
          No pending patches. Run <code className="text-latent-accent">latentcode scan --judge llm</code> to generate them.
        </div>
      )}

      <div className="grid grid-cols-1 gap-3">
        {pending.map((p: any) => (
          <PatchCard key={p.id} item={p} />
        ))}
      </div>
    </div>
  );
}