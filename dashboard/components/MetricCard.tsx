export default function MetricCard({
  label,
  value,
  hint,
}: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="lc-card">
      <div className="text-xs uppercase tracking-wider text-gray-500">{label}</div>
      <div className="text-2xl font-semibold mt-2">{value}</div>
      {hint && <div className="text-xs text-gray-500 mt-1">{hint}</div>}
    </div>
  );
}