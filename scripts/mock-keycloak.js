#!/usr/bin/env node
/**
 * mock-keycloak.js — DEPLOYMENT SHIM for the local (dockerless) demo environment.
 *
 * FIX (demo-runtime): `services/_demo_oidc_shim.py` documents this file, but it
 * was never shipped in the archive — every dockerless demo attempt failed at
 * /v1/keycloak/config discovery with ECONNREFUSED on :9080. This shim restores
 * the documented behaviour:
 *
 *   GET  /realms/hsaai/protocol/openid-connect/auth     — minimal login page (auto-submit for demo)
 *   POST /realms/hsaai/protocol/openid-connect/token    — PKCE code exchange (RS256 JWT)
 *   GET  /realms/hsaai/protocol/openid-connect/certs    — JWKS (public RSA key)
 *   GET  /realms/hsaai/protocol/openid-connect/userinfo — claims for the access token
 *   GET  /realms/hsaai/protocol/openid-connect/logout   — end-session redirect
 *
 * This file is demo infrastructure only — NOT part of the product codebase.
 * Demo credentials are intentionally non-secret (demo environment, no real IdP).
 *
 * Run with:  node scripts/mock-keycloak.js   (listens on 127.0.0.1:9080)
 */
"use strict";

const http = require("http");
const crypto = require("crypto");

const PORT = parseInt(process.env.MOCK_KEYCLOAK_PORT || "9080", 10);
const HOST = process.env.MOCK_KEYCLOAK_HOST || "127.0.0.1";
const REALM = process.env.KEYCLOAK_REALM || "hsaai";
const BASE = `/realms/${REALM}/protocol/openid-connect`;
const CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID || "hsaai-frontend";
const CLIENT_SECRET = process.env.KEYCLOAK_CLIENT_SECRET || "hsaai-demo-secret";
const ACCESS_TTL = parseInt(process.env.MOCK_ACCESS_TTL || "900", 10); // 15 min
const REFRESH_TTL = 86400;

// ---------------------------------------------------------------------------
// Demo identity (documented, intentionally fake — no real credentials involved)
// ---------------------------------------------------------------------------
const DEMO_USER = {
  sub: "f1a2b3c4-0000-4000-8000-demo000001",
  preferred_username: "مدير النظام",
  email: "admin@demo.hsaai.local",
  roles: ["hsaai_admin", "ai_user", "ai_admin", "audit_viewer"],
  tenant_id: "hsa-enterprise",
  workspace_id: "hq-main",
  department: "الإدارة التنفيذية",
};

// ---------------------------------------------------------------------------
// RSA keypair (generated at boot; stable for the lifetime of the process)
// KeyObjects (no encoding) so we can export the JWK and sign with the same pair.
// ---------------------------------------------------------------------------
const { publicKey, privateKey } = crypto.generateKeyPairSync("rsa", {
  modulusLength: 2048,
});

function b64url(buf) {
  return Buffer.from(buf).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// JWKS from the public key (n + e in base64url)
function jwksFor(kid) {
  const jwk = publicKey.export({ format: "jwk" });
  return { keys: [{ kty: "RSA", kid, use: "sig", alg: "RS256", n: jwk.n, e: jwk.e }] };
}
const KID = "mock-keycloak-key-1";

function baseJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { "Content-Type": "application/json", "Cache-Control": "no-store", "Content-Length": Buffer.byteLength(body) });
  res.end(body);
}

function signJwt(payload) {
  const header = { alg: "RS256", typ: "JWT", kid: KID };
  const now = Math.floor(Date.now() / 1000);
  const p = Object.assign({}, payload, { iat: now });
  const h = b64url(JSON.stringify(header));
  const d = b64url(JSON.stringify(p));
  const signer = crypto.createSign("RSA-SHA256");
  signer.update(`${h}.${d}`);
  const sig = signer.sign(privateKey, "base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${h}.${d}.${sig}`;
}

function issueTokens(extraClaims) {
  const iss = `http://${HOST}:${PORT}/realms/${REALM}`;
  const base = {
    iss,
    sub: DEMO_USER.sub,
    preferred_username: DEMO_USER.preferred_username,
    email: DEMO_USER.email,
    email_verified: true,
    name: DEMO_USER.preferred_username,
    // aud is an ARRAY so both the web middleware (hsaai-frontend) and the
    // backend shim (hsaai-api) verify successfully against the same token.
    aud: [CLIENT_ID, "hsaai-api"],
    azp: CLIENT_ID,
    realm_access: { roles: DEMO_USER.roles },
    roles: DEMO_USER.roles,
    tenant_id: DEMO_USER.tenant_id,
    workspace_id: DEMO_USER.workspace_id,
    department: DEMO_USER.department,
    scope: "openid profile email roles",
    typ: "Bearer",
  };
  Object.assign(base, extraClaims || {});
  const access = signJwt(Object.assign({}, base, { exp: Math.floor(Date.now() / 1000) + ACCESS_TTL, token_type: "Bearer" }));
  const refresh = signJwt(Object.assign({}, base, { exp: Math.floor(Date.now() / 1000) + REFRESH_TTL, typ: "Refresh" }));
  const idToken = signJwt(Object.assign({}, base, { aud: CLIENT_ID, exp: Math.floor(Date.now() / 1000) + ACCESS_TTL }));
  return { access_token: access, refresh_token: refresh, id_token: idToken, expires_in: ACCESS_TTL, refresh_expires_in: REFRESH_TTL, token_type: "Bearer", scope: "openid profile email roles" };
}

// pending authorization codes: code -> { challenge, challenge_method, redirect_uri, client_id }
const pendingCodes = new Map();

function loginPage(redirectParams) {
  const qs = new URLSearchParams(redirectParams).toString();
  return `<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>HSAAI — تسجيل الدخول الموحّد (Demo IdP)</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; font-family: "IBM Plex Sans Arabic","Segoe UI",Tahoma,sans-serif; }
  body { margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center; background:#FAFAF9; }
  .strip { position:fixed; top:0; right:0; left:0; height:4px; background:linear-gradient(to left,#F4C430,#A67C00,#F4C430); }
  .card { width:400px; background:#fff; border:1px solid #E7E5E4; border-radius:16px; padding:32px; box-shadow:0 8px 24px rgba(17,17,17,.06); }
  .logo { display:flex; align-items:center; gap:12px; justify-content:center; margin-bottom:8px; }
  .mark { width:44px; height:44px; border-radius:12px; border:2px solid #F4C430; display:flex; align-items:center; justify-content:center; font-weight:700; color:#A67C00; }
  h1 { font-size:18px; color:#111; text-align:center; margin:8px 0 2px; }
  p.sub { font-size:12px; color:#64748B; text-align:center; margin:0 0 20px; }
  label { display:block; font-size:12px; color:#64748B; margin:12px 0 4px; font-weight:600; }
  input { width:100%; padding:10px 12px; border:1px solid #E7E5E4; border-radius:10px; font-size:14px; color:#111; background:#fff; }
  input:focus { outline:2px solid #F4C430; border-color:#A67C00; }
  button { width:100%; margin-top:20px; padding:11px; border:0; border-radius:10px; background:#F4C430; color:#111; font-weight:700; font-size:14px; cursor:pointer; }
  button:hover { background:#A67C00; color:#fff; }
  .badge { margin-top:16px; font-size:11px; color:#A67C00; text-align:center; background:#FDF4E3; border-radius:8px; padding:8px; }
  .realm { display:flex; justify-content:space-between; font-size:11px; color:#64748B; margin-top:14px; }
  .realm b { color:#111; }
</style>
</head>
<body>
<div class="strip"></div>
<form class="card" method="get" action="${BASE}/auth/submit">
  <input type="hidden" name="qs" value="${qs.replace(/"/g, "&quot;")}"/>
  <div class="logo"><div class="mark">HSAAI</div></div>
  <h1>تسجيل الدخول الموحّد</h1>
  <p class="sub">بيئة العرض التجريبية — HSAAI Enterprise Demo IdP</p>
  <label>اسم المستخدم</label>
  <input name="username" value="${DEMO_USER.preferred_username}" readonly/>
  <label>كلمة المرور</label>
  <input name="password" type="password" value="••••••••" readonly/>
  <button type="submit">تسجيل الدخول</button>
  <div class="badge">حساب عرض تجريبي — Demo account</div>
  <div class="realm"><span>Realm</span><b>hsaai</b></div>
</form>
</body>
</html>`;
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const path = url.pathname;

  // --- OIDC discovery-ish endpoints the demo needs ---
  if (path === `${BASE}/certs` && req.method === "GET") return baseJson(res, 200, jwksFor(KID));

  if (path === `${BASE}/auth` && req.method === "GET") {
    const p = Object.fromEntries(url.searchParams.entries());
    if (!p.redirect_uri || !p.client_id) return baseJson(res, 400, { error: "invalid_request", error_description: "redirect_uri and client_id are required" });
    return res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }).end(loginPage(p));
  }

  // Form submit → issue code → redirect back
  if (path === `${BASE}/auth/submit` && req.method === "GET") {
    const wrapped = new URLSearchParams(url.searchParams.get("qs") || "");
    const redirectUri = wrapped.get("redirect_uri");
    const state = wrapped.get("state");
    const challenge = wrapped.get("code_challenge");
    const method = wrapped.get("code_challenge_method") || "S256";
    const clientId = wrapped.get("client_id");
    if (!redirectUri) return baseJson(res, 400, { error: "invalid_request" });
    const code = crypto.randomBytes(24).toString("hex");
    pendingCodes.set(code, { challenge, method, redirect_uri: redirectUri, client_id: clientId, ts: Date.now() });
    const back = new URL(redirectUri);
    back.searchParams.set("code", code);
    if (state) back.searchParams.set("state", state);
    res.writeHead(302, { Location: back.toString() });
    return res.end();
  }

  // Token endpoint (authorization_code + refresh_token grants)
  if (path === `${BASE}/token` && req.method === "POST") {
    let body = "";
    req.on("data", (c) => (body += c));
    return req.on("end", () => {
      const form = new URLSearchParams(body);
      const grant = form.get("grant_type");
      const clientId = form.get("client_id");
      const secret = form.get("client_secret");
      if (clientId !== CLIENT_ID || (secret !== CLIENT_SECRET && grant !== "refresh_token")) {
        return baseJson(res, 401, { error: "invalid_client", error_description: "client authentication failed" });
      }
      if (grant === "authorization_code") {
        const code = form.get("code");
        const verifier = form.get("code_verifier");
        const redirectUri = form.get("redirect_uri");
        const rec = pendingCodes.get(code);
        if (!rec) return baseJson(res, 400, { error: "invalid_grant", error_description: "unknown or reused code" });
        pendingCodes.delete(code);
        if (rec.redirect_uri !== redirectUri) return baseJson(res, 400, { error: "invalid_grant", error_description: "redirect_uri mismatch" });
        if (rec.challenge) {
          // PKCE S256
          const digest = crypto.createHash("sha256").update(verifier || "").digest("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
          if (digest !== rec.challenge) return baseJson(res, 400, { error: "invalid_grant", error_description: "PKCE verification failed" });
        }
        return baseJson(res, 200, issueTokens());
      }
      if (grant === "refresh_token") {
        const rt = form.get("refresh_token");
        if (!rt) return baseJson(res, 400, { error: "invalid_request" });
        // Signature check (expiry not enforced strictly in demo)
        try {
          const parts = rt.split(".");
          const verifier = crypto.createVerify("RSA-SHA256");
          verifier.update(`${parts[0]}.${parts[1]}`);
          if (!verifier.verify(publicKey, Buffer.from(parts[2].replace(/-/g, "+").replace(/_/g, "/"), "base64"))) throw new Error("bad signature");
        } catch {
          return baseJson(res, 400, { error: "invalid_grant", error_description: "refresh token signature invalid" });
        }
        return baseJson(res, 200, issueTokens());
      }
      return baseJson(res, 400, { error: "unsupported_grant_type" });
    });
  }

  if (path === `${BASE}/userinfo` && req.method === "GET") {
    const auth = req.headers.authorization || "";
    const token = auth.replace(/^Bearer\s+/i, "");
    try {
      const parts = token.split(".");
      const verifier = crypto.createVerify("RSA-SHA256");
      verifier.update(`${parts[0]}.${parts[1]}`);
      if (!verifier.verify(publicKey, Buffer.from(parts[2].replace(/-/g, "+").replace(/_/g, "/"), "base64"))) throw new Error("bad");
      const claims = JSON.parse(Buffer.from(parts[1].replace(/-/g, "+").replace(/_/g, "/"), "base64").toString());
      return baseJson(res, 200, { sub: claims.sub, preferred_username: claims.preferred_username, email: claims.email, roles: claims.roles, tenant_id: claims.tenant_id, workspace_id: claims.workspace_id });
    } catch {
      return baseJson(res, 401, { error: "invalid_token" });
    }
  }

  if (path === `${BASE}/logout` && req.method === "GET") {
    const post = url.searchParams.get("post_logout_redirect_uri") || url.searchParams.get("redirect_uri") || "/";
    res.writeHead(302, { Location: post });
    return res.end();
  }

  if (path === "/health") return baseJson(res, 200, { status: "ok", service: "mock-keycloak", realm: REALM });

  return baseJson(res, 404, { error: "not_found", path });
});

// Expire pending codes after 10 minutes to avoid unbounded growth
setInterval(() => {
  const cutoff = Date.now() - 600000;
  for (const [k, v] of pendingCodes) if (v.ts < cutoff) pendingCodes.delete(k);
}, 60000).unref();

server.listen(PORT, HOST, () => {
  console.log(`[mock-keycloak] Demo IdP listening on http://${HOST}:${PORT}/realms/${REALM} (client: ${CLIENT_ID})`);
  console.log(`[mock-keycloak] Demo user: ${DEMO_USER.preferred_username} (roles: ${DEMO_USER.roles.join(", ")})`);
});
