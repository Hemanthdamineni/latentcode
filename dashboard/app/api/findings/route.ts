// Next.js API route — proxies GET /api/findings to the latentcode serve
// backend. This avoids CORS issues when the dashboard (port 3000) tries
// to call the backend (port 7331) from the browser.
//
// The browser only sees same-origin requests; this route handles the
// cross-origin hop on the server side.

import { NextResponse } from "next/server";

const BACKEND = process.env.LATENTCODE_API_BASE || process.env.NEXT_PUBLIC_LATENTCODE_API || "http://127.0.0.1:7331";

export const dynamic = "force-dynamic";  // never cache

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/findings`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: `backend returned ${res.status}` },
        { status: 502 },
      );
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json(
      { error: `backend unreachable at ${BACKEND}: ${e?.message || e}` },
      { status: 502 },
    );
  }
}