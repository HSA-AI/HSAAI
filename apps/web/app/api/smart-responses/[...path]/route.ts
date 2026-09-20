/**
 * FIX (demo-runtime D-3): the Smart Responses admin page
 * (app/admin/smart-responses/page.tsx) calls Next-internal routes
 * `/api/smart-responses/*` (list, analytics, update, toggle, delete), but no
 * such route handlers existed — the admin screen rendered zero templates and
 * every action failed with 404.
 *
 * This catch-all proxy forwards to the backend Smart Responses router
 * (`/v1/smart-responses/*` in services/backend_core/smart_responses/router.py),
 * converting the httpOnly session cookie into an Authorization: Bearer header
 * (same pattern as lib/server-auth.ts buildBackendHeaders).
 */
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export const dynamic = "force-dynamic";

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8080";

async function proxy(request: NextRequest, subpath: string[]) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("hsaai_access_token")?.value;

  const suffix = subpath.join("/");
  const url = `${BACKEND_URL}/v1/smart-responses/${suffix}`;
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
    const response = await fetch(url, {
      method,
      headers,
      body,
      cache: "no-store",
    });
    const text = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";
    return new NextResponse(text, {
      status: response.status,
      headers: { "Content-Type": contentType },
    });
  } catch (err) {
    return NextResponse.json(
      { detail: `Backend unreachable: ${err instanceof Error ? err.message : "unknown"}` },
      { status: 502 },
    );
  }
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function POST(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function PUT(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function PATCH(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
export async function DELETE(request: NextRequest, ctx: Ctx) {
  return proxy(request, (await ctx.params).path);
}
