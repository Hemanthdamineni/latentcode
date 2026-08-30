"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/findings", label: "Findings" },
  { href: "/graph", label: "Dependency graph" },
  { href: "/metrics", label: "Metrics" },
  { href: "/repairs", label: "Repair queue" },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-[200px] shrink-0 border-r flex flex-col"
           style={{ background: "var(--lc-surface)", borderColor: "var(--lc-border)" }}>
      {/* Brand mark */}
      <div className="px-5 pt-5 pb-6 flex items-center gap-2.5">
        {/* Mark: an inset square with a single amber pixel — the "latent" */}
        <div className="relative w-[18px] h-[18px] rounded-[3px]"
             style={{ background: "var(--lc-bg)", border: "1px solid var(--lc-border-strong)" }}>
          <div className="absolute inset-[5px] rounded-[1px]"
               style={{ background: "var(--lc-accent)" }} />
        </div>
        <div>
          <div className="text-[13px] font-semibold tracking-[-0.01em] leading-none"
               style={{ color: "var(--lc-text)" }}>LatentCode</div>
          <div className="text-[10px] uppercase tracking-[0.12em] mt-1"
               style={{ color: "var(--lc-text-mute)" }}>v0.3 · dev</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3">
        <div className="lc-h2 px-2 mb-2">Workspace</div>
        <ul className="flex flex-col gap-px">
          {NAV.map((n) => {
            const active = n.href === "/" ? pathname === "/" : pathname?.startsWith(n.href);
            return (
              <li key={n.href}>
                <Link
                  href={n.href}
                  className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-[5px] text-[13px] transition-colors"
                  style={{
                    background: active ? "var(--lc-surface-2)" : "transparent",
                    color: active ? "var(--lc-text)" : "var(--lc-text-dim)",
                    fontWeight: active ? 500 : 400,
                  }}
                >
                  {active && (
                    <span className="w-[3px] h-3 rounded-full"
                          style={{ background: "var(--lc-accent)" }} />
                  )}
                  {n.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t text-[11px]"
           style={{ borderColor: "var(--lc-border)", color: "var(--lc-text-mute)" }}>
        <a href="https://github.com/Hemanthdamineni/latentcode"
           className="hover:underline"
           style={{ color: "var(--lc-text-dim)" }}>
          github.com/Hemanthdamineni/latentcode ↗
        </a>
      </div>
    </aside>
  );
}