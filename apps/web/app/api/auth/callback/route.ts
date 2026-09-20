import { NextRequest, NextResponse } from "next/server";
import { exchangeCodeForTokens } from "@/lib/server-auth"; // FIX C-06: server-safe import (was @/lib/auth-provider — client module, broke OIDC flow)

/**
 * GET /api/auth/callback
 *
 * OIDC Authorization Code Flow — callback handler.
 * Keycloak redirects here after the user authenticates. We exchange the
 * `code` for access/refresh tokens, set them as httpOnly cookies, and
 * redirect to the original requested URL (or "/" by default).
 *
 * FIX v2.1 (P0): This route was missing, breaking the entire OIDC flow.
 * The AuthProvider in lib/auth-provider.ts points redirect_uri here, but
 * the route did not exist — every login attempt dead-ended at a 404.
 */

// Force dynamic rendering — this route uses cookies and must not be statically generated.
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;

  // FIX C-09: derive the external origin from forwarding headers once —
  // Next standalone may expose the bind address (0.0.0.0) in request.url,
  // which breaks redirects and cookie scope after the OIDC callback.
  const _extOrigin = (() => {
    const h = request.headers;
    const proto = h.get("x-forwarded-proto") || "http";
    const host = h.get("x-forwarded-host") || h.get("host") || new URL(request.url).host;
    return `${proto}://${host}`;
  })();
  const code = params.get("code");
  const state = params.get("state");
  const error = params.get("error");
  const errorDescription = params.get("error_description");

  if (error) {
    const msg = encodeURIComponent(errorDescription || error);
    return NextResponse.redirect(new URL(`/login?reason=error&message=${msg}`, _extOrigin));
  }

  if (!code || !state) {
    return NextResponse.redirect(new URL("/login?reason=error", _extOrigin));
  }

  // Verify state parameter against the one stored by AuthProvider before redirect.
  // The state is stored in a short-lived httpOnly cookie "hsaai_auth_state".
  const cookieState = request.cookies.get("hsaai_auth_state")?.value;
  if (!cookieState || cookieState !== state) {
    return NextResponse.redirect(new URL("/login?reason=error&message=state_mismatch", _extOrigin));
  }

  // Determine the original redirect target (encoded in state).
  // AuthProvider sets state = `${randomNonce}::${btoa(originalPath)}`.
  let returnTo = "/";
  try {
    const sepIdx = state.indexOf("::");
    if (sepIdx > 0) {
      const encoded = state.slice(sepIdx + 2);
      returnTo = Buffer.from(encoded, "base64").toString("utf-8");
      // Guard against open-redirect: only allow relative paths.
      if (!returnTo.startsWith("/") || returnTo.startsWith("//")) {
        returnTo = "/";
      }
    }
  } catch {
    returnTo = "/";
  }

  try {
    // FIX F-04: Read the PKCE verifier from the httpOnly cookie set by /api/auth/start.
    const codeVerifier = request.cookies.get("hsaai_pkce_verifier")?.value;
    if (!codeVerifier) {
      return NextResponse.redirect(new URL("/login?reason=error&message=missing_pkce_verifier", _extOrigin));
    }
    // FIX C-07: reconstruct the redirect_uri from forwarding headers.
    // request.url (a) includes ?code&state query and (b) may carry the server
    // bind address (e.g. 0.0.0.0) — Keycloak requires an EXACT match with the
    // redirect_uri used at /api/auth/start, so derive it from Host headers.
    const _h = request.headers;
    const _proto = _h.get("x-forwarded-proto") || "http";
    const _host = _h.get("x-forwarded-host") || _h.get("host") || new URL(request.url).host;
    const redirectUri = `${_proto}://${_host}/api/auth/callback`;
    const tokenResponse = await exchangeCodeForTokens(code, redirectUri, codeVerifier);
    const response = NextResponse.redirect(new URL(returnTo, _extOrigin));

    // Set httpOnly, Secure, SameSite=Strict cookies for the tokens.
    const secure = (process.env.HSAAI_COOKIE_SECURE ?? String(process.env.NODE_ENV === "production")) === "true"; // FIX C-08: configurable Secure flag (required for plain-HTTP demo deployments)
    const cookieOpts = {
      httpOnly: true,
      secure,
      sameSite: "strict" as const,
      path: "/",
      maxAge: 60 * 60 * 8, // 8 hours
    };

    response.cookies.set("hsaai_access_token", tokenResponse.access_token, cookieOpts);
    if (tokenResponse.refresh_token) {
      response.cookies.set("hsaai_refresh_token", tokenResponse.refresh_token, {
        ...cookieOpts,
        maxAge: 60 * 60 * 24 * 30, // 30 days
      });
    }
    // Clear the one-time state + PKCE cookies.
    response.cookies.delete("hsaai_auth_state");
    response.cookies.delete("hsaai_pkce_verifier");

    return response;
  } catch (e) {
    console.error("Token exchange failed:", e);
    return NextResponse.redirect(new URL("/login?reason=error&message=token_exchange_failed", _extOrigin));
  }
}
