import { NextRequest, NextResponse } from "next/server";
import { exchangeCodeForTokens } from "@/lib/auth-provider";

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
  const code = params.get("code");
  const state = params.get("state");
  const error = params.get("error");
  const errorDescription = params.get("error_description");

  if (error) {
    const msg = encodeURIComponent(errorDescription || error);
    return NextResponse.redirect(new URL(`/login?reason=error&message=${msg}`, request.url));
  }

  if (!code || !state) {
    return NextResponse.redirect(new URL("/login?reason=error", request.url));
  }

  // Verify state parameter against the one stored by AuthProvider before redirect.
  // The state is stored in a short-lived httpOnly cookie "hsaai_auth_state".
  const cookieState = request.cookies.get("hsaai_auth_state")?.value;
  if (!cookieState || cookieState !== state) {
    return NextResponse.redirect(new URL("/login?reason=error&message=state_mismatch", request.url));
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
      return NextResponse.redirect(new URL("/login?reason=error&message=missing_pkce_verifier", request.url));
    }
    const tokenResponse = await exchangeCodeForTokens(code, request.url, codeVerifier);
    const response = NextResponse.redirect(new URL(returnTo, request.url));

    // Set httpOnly, Secure, SameSite=Strict cookies for the tokens.
    const secure = process.env.NODE_ENV === "production";
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
    return NextResponse.redirect(new URL("/login?reason=error&message=token_exchange_failed", request.url));
  }
}
