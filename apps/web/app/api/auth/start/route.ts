/**
 * FIX F-04: /api/auth/start — server-side PKCE state initialization.
 *
 * Previously the auth-provider stored the PKCE verifier in sessionStorage, but
 * the callback route reads state from a cookie — they never matched.
 * This route stores both state and code_verifier in httpOnly cookies that the
 * callback route can read.
 */
import { NextRequest, NextResponse } from "next/server";
import { randomBytes, createHash } from "crypto";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const returnTo: string = body.returnTo || "/";

  // Open-redirect guard
  if (!returnTo.startsWith("/") || returnTo.startsWith("//")) {
    return NextResponse.json({ error: "Invalid return path" }, { status: 400 });
  }

  // Generate PKCE verifier + challenge + state
  const codeVerifier = randomBytes(32).toString("base64url");
  const codeChallenge = createHash("sha256").update(codeVerifier).digest("base64url");
  const state = randomBytes(16).toString("hex");

  // Encode the return path in state so callback knows where to send the user
  const encodedReturn = Buffer.from(returnTo, "utf-8").toString("base64url");
  const fullState = `${state}::${encodedReturn}`;

  const secure = process.env.NODE_ENV === "production";
  const cookieOpts = {
    httpOnly: true,
    secure,
    sameSite: "lax" as const,
    path: "/",
    maxAge: 600, // 10 minutes — should be enough for OIDC redirect
  };

  const response = NextResponse.json({
    codeChallenge,
    codeChallengeMethod: "S256",
    state: fullState,
  });

  response.cookies.set("hsaai_auth_state", fullState, cookieOpts);
  response.cookies.set("hsaai_pkce_verifier", codeVerifier, cookieOpts);

  return response;
}
