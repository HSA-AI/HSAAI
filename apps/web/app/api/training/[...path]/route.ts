/**
 * HSAAI Model Training API Proxy Route Handler v3.0
 * ═══════════════════════════════════════════════════════════════════════
 *
 * CRITICAL FIX (V3): This route handler proxies browser requests to the
 * model-training FastAPI service (running on port 8090). The service uses
 * service-auth (not browser cookies), so we forward the user's JWT from
 * the httpOnly cookie as the X-Service-Auth header.
 *
 * This replaces the broken pattern where the browser directly called
 * /api/training/* which hit Next.js's 404 HTML page.
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const MODEL_TRAINING_URL = process.env.MODEL_TRAINING_SERVICE_URL ||
  process.env.INTERNAL_MODEL_TRAINING_API_URL ||
  "http://model-training:8090";

async function handler(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path: pathSegments } = await context.params;
  const path = pathSegments.join("/");
  const url = `${MODEL_TRAINING_URL}/api/training/${path}${req.nextUrl.search}`;

  // Get the user's JWT from the httpOnly cookie
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("hsaai_access_token")?.value;

  // Build headers — forward auth + content type
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept": "application/json",
  };

  if (accessToken) {
    headers["X-Service-Auth"] = `Bearer ${accessToken}`;
  }

  // Forward the request to the model-training service
  try {
    const response = await fetch(url, {
      method: req.method,
      headers,
      body: req.method !== "GET" && req.method !== "HEAD" ? await req.text() : undefined,
      cache: "no-store",
    });

    // Get the response content type
    const contentType = response.headers.get("content-type") || "";

    // If the backend returned HTML (e.g., 404 page), return a JSON error instead
    if (contentType.includes("text/html")) {
      return NextResponse.json(
        {
          detail: `Model Training service returned HTML instead of JSON (status ${response.status})`,
          status: response.status,
          service: "model-training",
        },
        { status: response.status >= 400 ? response.status : 502 }
      );
    }

    // If JSON, forward the response
    if (contentType.includes("application/json")) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    }

    // For any other content type, return as text (safely)
    const text = await response.text();
    return NextResponse.json(
      { detail: text.slice(0, 500), status: response.status },
      { status: response.status }
    );
  } catch (error) {
    // Network error — backend unreachable
    return NextResponse.json(
      {
        detail: "Model Training service is unreachable. Please ensure the service is running.",
        error: error instanceof Error ? error.message : "Unknown error",
        service: "model-training",
      },
      { status: 503 }
    );
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
