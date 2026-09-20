import { NextRequest, NextResponse } from "next/server";
export const dynamic = "force-dynamic";
export async function GET(request: NextRequest) {
  const origin = process.env.APP_PUBLIC_URL || request.nextUrl.origin;
  const returnTo = request.nextUrl.searchParams.get("redirect") || "/";
  if (!returnTo.startsWith("/") || returnTo.startsWith("//") || returnTo.includes("\\")) {
    return NextResponse.json({ error: "Invalid redirect" }, { status: 400 });
  }
  const token = request.cookies.get("hsaai_refresh_token")?.value;
  if (!token) return NextResponse.redirect(new URL("/login?reason=session_expired", origin));
  try {
    const response = await fetch(`${process.env.AUTH_SERVICE_URL || "http://127.0.0.1:8010"}/v1/auth/refresh`, {
      method: "POST", cache: "no-store", signal: AbortSignal.timeout(15000),
      headers: { Cookie: `hsaai_refresh_token=${token}`, Origin: origin, "X-Requested-With": "XMLHttpRequest" },
    });
    if (!response.ok) throw new Error("Refresh refused");
    const result = NextResponse.redirect(new URL(returnTo, origin));
    for (const cookie of response.headers.getSetCookie()) result.headers.append("Set-Cookie", cookie);
    result.headers.set("Cache-Control", "no-store");
    return result;
  } catch {
    const result = NextResponse.redirect(new URL("/login?reason=session_expired", origin));
    result.cookies.delete("hsaai_access_token");
    result.cookies.delete("hsaai_refresh_token");
    return result;
  }
}
