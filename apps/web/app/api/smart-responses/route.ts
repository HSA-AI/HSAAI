/**
 * FIX (demo-runtime D-3, base path): the Smart Responses admin page also calls
 * `/api/smart-responses` (no subpath) for GET (list) and POST (create). The
 * catch-all under [...path] cannot match an empty suffix, so this handler
 * proxies the collection endpoints to the backend router mounted at
 * /v1/smart-responses (services/backend_core/smart_responses/router.py).
 */
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export const dynamic = "force-dynamic";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8080";

async function proxyCollection(request: NextRequest) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("hsaai_access_token")?.value;

  const url = `${BACKEND_URL}/v1/smart-responses`;
  const method = request.method;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
  };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  let body: string | undefined;
  if (method !== "GET" && method !== "HEAD") {
    body = JSON.stringify(await request.json().catch(() => ({})));
  }

  try {
    const response = await fetch(url, { method, headers, body, cache: "no-store" });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      { detail: `Backend unreachable: ${err instanceof Error ? err.message : "unknown"}` },
      { status: 502 },
    );
  }
}

export async function GET(request: NextRequest) {
  return proxyCollection(request);
}
export async function POST(request: NextRequest) {
  return proxyCollection(request);
}
