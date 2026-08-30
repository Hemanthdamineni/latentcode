"use client";
import { usePathname } from "next/navigation";

const TITLES: Record<string, { title: string; sub: string }> = {
  "/":          { title: "Overview",        sub: "Latest scan summary and the issues that need attention." },
  "/findings":  { title: "Findings",        sub: "All detected defects, sorted by severity." },
  "/graph":     { title: "Dependency graph", sub: "Symbols, imports, and routes — the substrate LatentCode reasons over." },
  "/metrics":   { title: "Metrics",         sub: "Per-category counts and aggregate health." },
  "/repairs":   { title: "Repair queue",    sub: "Patches proposed by the LLM, waiting on human approval." },
};

function titleFor(path: string) {
  if (TITLES[path]) return TITLES[path];
  for (const k of Object.keys(TITLES)) {
    if (path?.startsWith(k) && k !== "/") return TITLES[k];
  }
  return TITLES["/"];
}

export default function Topbar() {
  const pathname = usePathname() || "/";
  const { title, sub } = titleFor(pathname);
  return (
    <div className="h-[68px] border-b flex items-center justify-between px-10"
         style={{ background: "var(--lc-bg)", borderColor: "var(--lc-border)" }}>
      <div>
        <div className="text-[20px] font-semibold tracking-[-0.01em]"
             style={{ color: "var(--lc-text)" }}>{title}</div>
        <div className="text-[12.5px] mt-0.5"
             style={{ color: "var(--lc-text-mute)" }}>{sub}</div>
      </div>
      <div className="flex items-center gap-3">
        <a href="https://github.com/Hemanthdamineni/latentcode"
           target="_blank" rel="noreferrer"
           className="text-[12px] px-3 py-1.5 rounded-[5px] border transition-colors"
           style={{ borderColor: "var(--lc-border)", color: "var(--lc-text-dim)" }}>
          GitHub ↗
        </a>
      </div>
    </div>
  );
}