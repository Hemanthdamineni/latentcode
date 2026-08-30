// Next.js API route — proxies GET /api/queue to the latentcode serve backend.

import { NextResponse } from "next/server";

const BACKEND = process.env.LATENTCODE_API_BASE || process.env.NEXT_PUBLIC_LATENTCODE_API || "http://127.0.0.1:7331";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/queue`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json(
        { error: `backend returned ${res.status}` },
        { status: 502 },
      );
    }
    return NextResponse.json(await res.json());
  } catch (e: any) {
    return NextResponse.json(
      { error: `backend unreachable: ${e?.message || e}` },
      { status: 502 },
    );
  }
}