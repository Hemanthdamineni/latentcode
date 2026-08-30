export default function Stat({
  label,
  value,
  accent = "accent",
}: { label: string; value: number | string; accent?: "accent" | "warn" | "danger" | "ok" | "muted" }) {
  const colorMap = {
    accent: "text-latent-accent",
    warn: "text-latent-warn",
    danger: "text-latent-danger",
    ok: "text-latent-ok",
    muted: "text-latent-muted",
  } as const;
  return (
    <div className="lc-card">
      <div className="text-xs uppercase tracking-wider text-gray-500">{label}</div>
      <div className={`text-3xl font-semibold mt-2 ${colorMap[accent]}`}>{value}</div>
    </div>
  );
}