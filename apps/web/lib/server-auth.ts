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

/**
 * FIX C-06 (v0.6.1 demo hardening): exchangeCodeForTokens moved here.
 *
 * The function previously lived in lib/auth-provider.tsx, which is a
 * "use client" module — invoking it from the /api/auth/callback Route Handler
 * threw "Attempted to call exchangeCodeForTokens() from the server but
 * exchangeCodeForTokens is on the client", breaking the entire OIDC login
 * flow (token exchange could never complete).
 *
 * This server-safe copy performs the back-channel PKCE token exchange with
 * Keycloak from the Route Handler runtime.
 */
export async function exchangeCodeForTokens(
  code: string,
  redirectUri: string,
  codeVerifier: string,
): Promise<{
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_in?: number;
}> {
  const keycloakUrl = process.env.KEYCLOAK_URL || "http://keycloak:8080";
  const realm = process.env.KEYCLOAK_REALM || "hsaai";
  const clientId = process.env.KEYCLOAK_CLIENT_ID || "hsaai-frontend";
  const clientSecret = process.env.KEYCLOAK_CLIENT_SECRET;

  if (!codeVerifier) {
    throw new Error("PKCE code_verifier is missing — cannot complete token exchange");
  }

  const tokenEndpoint = `${keycloakUrl}/realms/${realm}/protocol/openid-connect/token`;

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    code_verifier: codeVerifier,
  });
  // PROD-RUNTIME FIX: hsaai-frontend is a public PKCE client. Add a secret only
  // when deployment explicitly configures a confidential client.
  if (clientSecret) body.set("client_secret", clientSecret);

  const response = await fetch(tokenEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Token exchange failed: ${response.status} ${errorText}`);
  }

  return response.json();
}
