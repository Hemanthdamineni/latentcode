import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "LatentCode",
  description: "AI-powered latent defect finder",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <aside className="w-56 bg-latent-panel border-r border-latent-border p-4 flex flex-col gap-1">
            <div className="mb-6">
              <div className="text-lg font-semibold tracking-tight">LatentCode</div>
              <div className="text-xs text-latent-muted">hidden defects, surfaced</div>
            </div>
            <NavLink href="/">Overview</NavLink>
            <NavLink href="/findings">Findings</NavLink>
            <NavLink href="/graph">Dependency graph</NavLink>
            <NavLink href="/metrics">Metrics</NavLink>
            <NavLink href="/repairs">Repair queue</NavLink>
          </aside>
          <main className="flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-latent-border hover:text-white transition"
    >
      {children}
    </Link>
  );
}