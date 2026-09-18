/**
 * Server-side findings loader.
 *
 * Reads from CODEMEND_FINDINGS env var (path to .codemend dir) or
 * falls back to the current working directory's .codemend directory.
 */
import { promises as fs } from "fs";
import path from "path";

const ROOT = process.env.CODEMEND_FINDINGS || path.join(process.cwd(), ".codemend");

export async function readFindings(): Promise<any | null> {
  try {
    const file = path.join(ROOT, "findings.json");
    const text = await fs.readFile(file, "utf-8");
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function readQueue(): Promise<any[]> {
  try {
    const file = path.join(ROOT, "approval_queue.json");
    const text = await fs.readFile(file, "utf-8");
    return JSON.parse(text).pending || [];
  } catch {
    return [];
  }
}

/**
 * Browser-side client to talk to the CodeMend serve backend.
 * Configure via NEXT_PUBLIC_CODEMEND_API (default: http://127.0.0.1:7331).
 */
const API_BASE = process.env.NEXT_PUBLIC_CODEMEND_API || "http://127.0.0.1:7331";

export async function approvePatch(id: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/queue/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  return res.json();
}

export async function rejectPatch(id: string, reason: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/queue/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, reason }),
  });
  return res.json();
}

export async function applyPatch(id: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/queue/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  return res.json();
}

export async function triggerRescan(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/rescan`, { method: "POST" });
  return res.json();
}