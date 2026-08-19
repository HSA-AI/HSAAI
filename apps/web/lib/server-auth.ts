/**
 * HSAAI Server-Side Auth Helpers (v2.0 — World-Class Audit Fix)
 *
 * SECURITY FIX v2.0: Replaces ALL insecure auth patterns found in v2.0 audit:
 *   - "Bearer admin" hardcoded fallback (51 files — fixed in v1.1)
 *   - "Bearer hsaai_admin" hardcoded fallback (3 files — fixed in v2.0)
 *   - "HSAAI_ADMIN_TOKEN ? ... : 'Bearer admin'" pattern (fixed in v1.1)
 *   - "HSAAI_DEV_TOKEN" with "Bearer admin" comment fallback (43 files — fixed in v1.1)
 *   - "AUTH_HEADER" undefined reference (4 files — fixed in v2.0)
 *
 * Authentication is now performed by forwarding the user's httpOnly
 * `hsaai_access_token` cookie (set by auth_service via Keycloak OIDC) to the
 * backend. No static tokens are ever sent.
 *
 * If the cookie is missing, the request is forwarded WITHOUT an Authorization
 * header — the backend returns 401, which the caller surfaces to the user.
 *
 * FIX FIX-MEDIUM-QUALITY (Issue 7): Next.js 15 makes cookies() async
 * (returns Promise<ReadonlyRequestCookies>). All helpers below are now async
 * and await cookies(). Callers must `await` them.
 */
import { cookies } from "next/headers";

export const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.AUTH_SERVICE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

/**
 * Build headers for an authenticated backend call from a Next.js Server
 * Component / Route Handler. Now async to await the Next.js 15 cookies() promise.
 */
export async function buildBackendHeaders(
  extra?: Record<string, string>,
): Promise<Record<string, string>> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("hsaai_access_token")?.value;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    ...(extra || {}),
  };

  if (accessToken && accessToken.length > 0) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  return headers;
}

/**
 * Build a fetch RequestInit for an authenticated backend call.
 * Now async because buildBackendHeaders is async.
 */
export async function backendFetchInit(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE" = "GET",
  body?: unknown,
): Promise<RequestInit> {
  const init: RequestInit = {
    method,
    headers: await buildBackendHeaders(),
    cache: "no-store",
  };
  if (body !== undefined && method !== "GET") {
    init.body = JSON.stringify(body);
  }
  return init;
}

/**
 * Forward the incoming request's cookies verbatim to the backend.
 * Now async to await the Next.js 15 cookies() promise.
 */
export async function forwardCookies(): Promise<string | undefined> {
  const cookieStore = await cookies();
  const all = cookieStore.getAll();
  if (all.length === 0) return undefined;
  return all.map((c) => `${c.name}=${c.value}`).join("; ");
}
