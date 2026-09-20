import { NextResponse } from "next/server";
export const dynamic = "force-dynamic";
export function GET() {
  return NextResponse.json({ status: "ok", service: "hsaai-web", version: "4.0.0-rc.1" }, { headers: { "Cache-Control": "no-store" } });
}
