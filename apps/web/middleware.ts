/**
 * HSAAI Next.js Middleware (v4.0)
 *
 * FIX F-03: Was only checking cookie EXISTENCE — any value (even empty) bypassed auth.
 * Now validates JWT signature using jose, enforces admin role on /admin/* paths,
 * and handles expired tokens by redirecting to refresh.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify, errors as joseErrors, createRemoteJWKSet } from "jose";

const PUBLIC_PATHS = [
  "/login",
  "/api/auth",
  "/api/health",
  "/_next",
  "/favicon.ico",
  "/manifest.webmanifest",
  "/sw.js",
  "/brand",
  "/hsaai_official_logo.png",
  "/hsaai-assistant-circle.png",
  "/hsaai-assistant-circle.svg",
];

const KEYCLOAK_ISSUER = process.env.KEYCLOAK_ISSUER || "http://keycloak:8080/realms/hsaai";
const KEYCLOAK_AUDIENCE = process.env.KEYCLOAK_AUDIENCE || "hsaai-frontend";
const JWKS_URI = `${KEYCLOAK_ISSUER.replace(/\/$/, "")}/protocol/openid-connect/certs`;

// FIX (runtime): use jose's createRemoteJWKSet — passing { keys: any[] } to
// jwtVerify is not type-compatible with the KeyLike union and broke the build.
// createRemoteJWKSet handles JWKS fetching + caching internally.
let _jwks: ReturnType<typeof createRemoteJWKSet> | null = null;
function getJwks() {
  if (!_jwks) {
    _jwks = createRemoteJWKSet(new URL(JWKS_URI));
  }
  return _jwks;
}

async function verifyToken(token: string): Promise<any | null> {
  try {
    const { payload } = await jwtVerify(token, getJwks(), {
      audience: KEYCLOAK_AUDIENCE,
      issuer: KEYCLOAK_ISSUER,
    });
    return payload;
  } catch (e) {
    if (e instanceof joseErrors.JWTExpired) {
      // Signal expired so caller can attempt refresh
      throw new Error("expired");
    }
    return null;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Check access token cookie
  const accessToken = request.cookies.get("hsaai_access_token")?.value;
  if (!accessToken) {
    const loginUrl = new URL("/login?reason=unauthenticated", request.url);
    return NextResponse.redirect(loginUrl);
  }

  // FIX F-03: Validate the JWT — was previously only checking cookie existence.
  let claims: any;
  try {
    claims = await verifyToken(accessToken);
  } catch (e: any) {
    if (e.message === "expired") {
      // Try refresh via /api/auth/refresh
      const refreshUrl = new URL("/api/auth/refresh", request.url);
      refreshUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(refreshUrl);
    }
    // Other verification error → redirect to login
    const loginUrl = new URL("/login?reason=invalid_token", request.url);
    return NextResponse.redirect(loginUrl);
  }

  if (!claims) {
    const loginUrl = new URL("/login?reason=invalid_token", request.url);
    return NextResponse.redirect(loginUrl);
  }

  // Enforce admin role on /admin/* paths
  const roles: string[] = claims.roles || claims.realm_access?.roles || [];
  if (pathname.startsWith("/admin") && !roles.includes("hsaai_admin")) {
    return new NextResponse("Forbidden: admin role required", { status: 403 });
  }

  // Add identity headers for downstream services (Edge runtime — cannot use httpOnly)
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-tenant-id", claims.tenant_id || "default");
  requestHeaders.set("x-user-id", claims.sub || "unknown");
  requestHeaders.set("x-user-roles", roles.join(","));

  return NextResponse.next({
    request: { headers: requestHeaders },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|manifest.webmanifest|sw.js|brand).*)"],
};
