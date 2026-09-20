#!/usr/bin/env node
/**
 * mock-keycloak.js — Local OIDC Identity Provider for HSAAI demo environment
 *
 * Implements the subset of the Keycloak protocol used by HSAAI:
 *   GET  /realms/hsaai/protocol/openid-connect/auth     (login form / SSO redirect)
 *   POST /realms/hsaai/protocol/openid-connect/auth     (credential check)
 *   POST /realms/hsaai/protocol/openid-connect/token    (authorization_code / refresh_token / password)
 *   GET  /realms/hsaai/protocol/openid-connect/certs    (JWKS)
 *   GET  /realms/hsaai/protocol/openid-connect/userinfo
 *   GET  /realms/hsaai/protocol/openid-connect/logout
 *   GET  /health
 *
 * Tokens: RS256, kid stable across restarts (keys persisted).
 * Audience: ["hsaai-frontend","hsaai-api"] so both web middleware and backend pass.
 *
 * DEMO credentials (masked on camera, documented in production notes):
 *   demo.admin / Hsaai@Demo2026  -> roles: hsaai_admin, ai_user
 *   demo.user / Hsaai@Demo2026   -> roles: ai_user
 */
"use strict";
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const PORT = parseInt(process.env.IDP_PORT || "9080", 10);
const ISSUER = `http://127.0.0.1:${PORT}/realms/hsaai`;
const REALM = "hsaai";
// v3 portable: data dir resolved from HSAAI_RUNTIME (set by hsaai-ctl/hsaai-env.sh),
// fallback: <project>/../runtime/data relative to this file
const DATA_DIR = process.env.HSAAI_DATA_DIR
  || (process.env.HSAAI_RUNTIME ? path.join(process.env.HSAAI_RUNTIME, "data")
      : path.join(__dirname, "..", "..", "..", "runtime", "data"));
const KEYFILE = path.join(DATA_DIR, "idp-keys.json");
const SESSION_COOKIE = "idp_session";
const SESSION_TTL = 3600;         // s
const ACCESS_TTL = 3600;          // s
const CODE_TTL = 120;             // s

// ---------- RSA key management (stable kid) ----------
function loadKeys() {
  try {
    const j = JSON.parse(fs.readFileSync(KEYFILE, "utf8"));
    if (j.kid && j.privatePem && j.publicJwk) return j;
  } catch (_) {}
  const { publicKey, privateKey } = crypto.generateKeyPairSync("rsa", {
    modulusLength: 2048, publicKeyEncoding: { type: "spki", format: "pem" },
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
  });
  const jwkRaw = crypto.createPublicKey(publicKey).export({ format: "jwk" });
  const kid = "hsaai-demo-" + crypto.randomBytes(4).toString("hex");
  const out = {
    kid,
    privatePem: privateKey,
    publicJwk: { kty: jwkRaw.kty, n: jwkRaw.n, e: jwkRaw.e, kid, alg: "RS256", use: "sig" },
  };
  fs.mkdirSync(path.dirname(KEYFILE), { recursive: true });
  fs.writeFileSync(KEYFILE, JSON.stringify(out, null, 2), { mode: 0o600 });
  return out;
}
const KEYS = loadKeys();

// ---------- demo users ----------
// SECURITY FIX (audit P1-2): demo passwords are now environment-overridable
// (MOCK_IDP_ADMIN_PASSWORD / MOCK_IDP_USER_PASSWORD). The committed defaults
// are ONLY for isolated local demos — this mock IdP must never front a real
// deployment (see deployment/production/install-systemd-units.sh, which
// refuses to install it unless HSAAI_ENABLE_DEMO_IDP=1).
const DEMO_DEFAULT_PASSWORD = process.env.MOCK_IDP_PASSWORD || "Hsaai@Demo2026";
const DEMO_ADMIN_PASSWORD = process.env.MOCK_IDP_ADMIN_PASSWORD || DEMO_DEFAULT_PASSWORD;
const DEMO_USER_PASSWORD = process.env.MOCK_IDP_USER_PASSWORD || DEMO_DEFAULT_PASSWORD;
const USERS = {
  "demo.admin": { username: "demo.admin", password: DEMO_ADMIN_PASSWORD, sub: "demo-admin-0001", name: "Demo Administrator",
                  email: "demo.admin@hsa-group.example", roles: ["hsaai_admin", "ai_user"] },
  "demo.user":  { username: "demo.user", password: DEMO_USER_PASSWORD, sub: "demo-user-0002", name: "Demo User",
                  email: "demo.user@hsa-group.example", roles: ["ai_user"] },
};

// ---------- state ----------
const sessions = new Map();  // sid -> {username, exp}
const codes = new Map();     // code -> {challenge, redirectUri, clientId, exp, username}

// ---------- helpers ----------
const b64u = (buf) => Buffer.from(buf).toString("base64url");
function signJwt(payload) {
  const header = b64u(JSON.stringify({ alg: "RS256", typ: "JWT", kid: KEYS.kid }));
  const body = b64u(JSON.stringify(payload));
  const signer = crypto.createSign("RSA-SHA256");
  signer.update(`${header}.${body}`);
  return `${header}.${body}.${b64u(signer.sign(KEYS.privatePem))}`;
}
function issueTokens(user, clientId, nonce) {
  const now = Math.floor(Date.now() / 1000);
  const base = {
    iss: ISSUER, aud: ["hsaai-frontend", "hsaai-api"], sub: user.sub,
    iat: now, exp: now + ACCESS_TTL, azp: clientId || "hsaai-frontend",
    typ: "Bearer", session_state: crypto.randomBytes(8).toString("hex"),
    preferred_username: user.username,
    email: user.email, name: user.name, given_name: user.name,
    tenant_id: "default", workspace_id: "default",
    roles: user.roles, realm_access: { roles: user.roles },
    scope: "openid profile email roles",
  };
  if (nonce) base.nonce = nonce;
  const access = signJwt(base);
  const idt = signJwt({ ...base, aud: clientId || "hsaai-frontend", nonce: nonce || undefined });
  const refresh = "rt_" + crypto.randomBytes(12).toString("hex") + "_" + user.username;
  return {
    access_token: access, refresh_token: refresh, id_token: idt,
    token_type: "Bearer", expires_in: ACCESS_TTL, refresh_expires_in: 14400,
    scope: "openid profile email roles", session_state: base.session_state,
  };
}
function parseCookies(req) {
  const out = {}; const raw = req.headers.cookie || "";
  raw.split(";").forEach((p) => { const i = p.indexOf("="); if (i > 0) out[p.slice(0, i).trim()] = decodeURIComponent(p.slice(i + 1).trim()); });
  return out;
}
function sessionUser(req) {
  const sid = parseCookies(req)[SESSION_COOKIE];
  if (!sid) return null;
  const s = sessions.get(sid);
  if (!s || s.exp < Date.now() / 1000) return null;
  return USERS[s.username] || null;
}
function redirect(res, url, headers = []) {
  res.writeHead(302, Object.assign({ Location: url }, Object.fromEntries(headers)));
  res.end();
}
function json(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
  res.end(body);
}

// ---------- login page (Scene 2 of the demo video) ----------
function loginPage(errorMsg, hidden) {
  const err = errorMsg
    ? `<div class="error" role="alert">${errorMsg}</div>`
    : "";
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HSAAI — Secure Sign In</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,'Segoe UI','Carlito','DejaVu Sans',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:radial-gradient(1200px 800px at 70% -10%,#12203a 0%,#0b1220 45%,#070b14 100%);color:#e7edf7}
  .wrap{width:420px;max-width:92vw}
  .brand{text-align:center;margin-bottom:28px}
  .logo{display:inline-flex;align-items:center;justify-content:center;width:64px;height:64px;border-radius:16px;
        background:linear-gradient(135deg,#e3b34e,#c98f2a);font-weight:800;font-size:22px;color:#04121f;letter-spacing:.5px}
  .brand h1{font-size:30px;font-weight:800;letter-spacing:2px;margin-top:14px;color:#f4f8ff}
  .brand p{font-size:12.5px;color:#8ea3c2;margin-top:6px;letter-spacing:.3px}
  .card{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);border-radius:14px;padding:30px;backdrop-filter:blur(6px)}
  label{display:block;font-size:12px;color:#9fb2cf;margin:14px 0 6px;letter-spacing:.4px;text-transform:uppercase}
  input{width:100%;padding:11px 12px;border-radius:8px;border:1px solid rgba(255,255,255,.14);background:rgba(8,14,26,.7);
        color:#eaf1fb;font-size:14px;outline:none}
  input:focus{border-color:#e3b34e;box-shadow:0 0 0 3px rgba(20,184,166,.15)}
  button{width:100%;margin-top:22px;padding:12px;border:0;border-radius:8px;cursor:pointer;font-size:14.5px;font-weight:700;
         background:linear-gradient(135deg,#e3b34e,#c98f2a);color:#03151f;letter-spacing:.3px}
  button:hover{filter:brightness(1.07)}
  .secure{display:flex;align-items:center;justify-content:center;gap:7px;margin-top:16px;font-size:11.5px;color:#7d92b3}
  .dot{width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 8px #22c55e88}
  .error{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.35);color:#fca5a5;padding:9px 12px;border-radius:8px;font-size:12.5px;margin-bottom:6px}
  .foot{text-align:center;font-size:11px;color:#5c6f8e;margin-top:22px}
</style></head>
<body><div class="wrap">
  <div class="brand"><div class="logo">HS</div><h1>HSAAI</h1><p>Enterprise AI Platform — Secure Authentication</p></div>
  <div class="card">
    ${err}
    <form method="POST" action="/realms/${REALM}/protocol/openid-connect/auth">
      ${hidden}
      <label for="username">Username or Email</label>
      <input id="username" name="username" autocomplete="username" placeholder="enterprise user" required>
      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" placeholder="••••••••" required>
      <button type="submit">Sign In</button>
    </form>
    <div class="secure"><span class="dot"></span> Secure Authentication · TLS · Session Encryption</div>
  </div>
  <div class="foot">Hayel Saeed Anam Artificial Intelligence · Internal Use Only</div>
</div></body></html>`;
}

// ---------- server ----------
const server = http.createServer((req, res) => {
  const u = new URL(req.url, `http://127.0.0.1:${PORT}`);
  const p = u.pathname;

  if (p === "/health") return json(res, 200, { status: "ok", service: "hsaai-demo-idp", issuer: ISSUER });

  const base = `/realms/${REALM}/protocol/openid-connect`;

  // --- JWKS ---
  if (p === `${base}/certs`) return json(res, 200, { keys: [KEYS.publicJwk] });

  // --- userinfo ---
  if (p === `${base}/userinfo`) {
    const auth = req.headers.authorization || "";
    const tok = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    try {
      const payload = JSON.parse(Buffer.from(tok.split(".")[1], "base64url").toString());
      return json(res, 200, { sub: payload.sub, preferred_username: payload.preferred_username,
        email: payload.email, name: payload.name, roles: payload.roles, tenant_id: payload.tenant_id });
    } catch (_) { return json(res, 401, { error: "invalid_token" }); }
  }

  // --- logout ---
  if (p === `${base}/logout`) {
    const sid = parseCookies(req)[SESSION_COOKIE];
    if (sid) sessions.delete(sid);
    return redirect(res, (u.searchParams.get("post_logout_redirect_uri") || "/") );
  }

  // --- authorize ---
  if (p === `${base}/auth`) {
    const qp = u.searchParams;
    if (req.method === "GET") {
      const user = sessionUser(req);
      if (user) {
        // existing SSO session -> issue code immediately
        const code = crypto.randomBytes(24).toString("hex");
        codes.set(code, { challenge: qp.get("code_challenge"), redirectUri: qp.get("redirect_uri"),
          clientId: qp.get("client_id"), exp: Date.now() / 1000 + CODE_TTL, username: user === USERS["demo.admin"] ? "demo.admin" : "demo.user" });
        const back = new URL(qp.get("redirect_uri") || "http://127.0.0.1:3000/api/auth/callback");
        back.searchParams.set("code", code);
        back.searchParams.set("state", qp.get("state") || "");
        return redirect(res, back.toString());
      }
      const hidden = ["client_id", "redirect_uri", "response_type", "scope", "code_challenge",
        "code_challenge_method", "state", "nonce"]
        .filter((k) => qp.get(k))
        .map((k) => `<input type="hidden" name="${k}" value="${qp.get(k)}">`).join("\n      ");
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
      return res.end(loginPage(null, hidden));
    }
    if (req.method === "POST") {
      let raw = "";
      req.on("data", (c) => (raw += c));
      req.on("end", () => {
        const form = new URLSearchParams(raw);
        const username = (form.get("username") || "").trim();
        const password = form.get("password") || "";
        const user = USERS[username];
        if (!user || user.password !== password) {
          res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
          const hidden = ["client_id", "redirect_uri", "response_type", "scope", "code_challenge",
            "code_challenge_method", "state", "nonce"]
            .filter((k) => form.get(k))
            .map((k) => `<input type="hidden" name="${k}" value="${form.get(k)}">`).join("\n      ");
          return res.end(loginPage("Invalid username or password. Please try again.", hidden));
        }
        const sid = crypto.randomBytes(16).toString("hex");
        sessions.set(sid, { username, exp: Date.now() / 1000 + SESSION_TTL });
        const code = crypto.randomBytes(24).toString("hex");
        codes.set(code, { challenge: form.get("code_challenge"), redirectUri: form.get("redirect_uri"),
          clientId: form.get("client_id"), exp: Date.now() / 1000 + CODE_TTL, username });
        const back = new URL(form.get("redirect_uri") || "http://127.0.0.1:3000/api/auth/callback");
        back.searchParams.set("code", code);
        back.searchParams.set("state", form.get("state") || "");
        res.setHeader("Set-Cookie", `${SESSION_COOKIE}=${sid}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_TTL}`);
        return redirect(res, back.toString());
      });
      return;
    }
  }

  // --- token ---
  if (p === `${base}/token` && req.method === "POST") {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      const form = new URLSearchParams(raw);
      const grant = form.get("grant_type");
      if (grant === "authorization_code") {
        const code = form.get("code");
        const rec = codes.get(code);
        if (!rec || rec.exp < Date.now() / 1000) return json(res, 400, { error: "invalid_grant", error_description: "code expired" });
        codes.delete(code);
        // PKCE S256 validation
        const verifier = form.get("code_verifier") || "";
        const digest = crypto.createHash("sha256").update(verifier).digest("base64url");
        if (!rec.challenge || digest !== rec.challenge)
          return json(res, 400, { error: "invalid_grant", error_description: "PKCE verification failed" });
        if (rec.redirectUri && form.get("redirect_uri") !== rec.redirectUri)
          return json(res, 400, { error: "invalid_grant", error_description: "redirect_uri mismatch" });
        const user = USERS[rec.username];
        return json(res, 200, issueTokens(user, form.get("client_id") || rec.clientId));
      }
      if (grant === "refresh_token") {
        // stateless demo refresh: accept tokens we issued (rt_*) by re-issuing from cookie username not possible;
        // instead the refresh token embeds the username
        const rt = form.get("refresh_token") || "";
        const m = /^rt_([a-f0-9]+)_([a-z.]+)$/.exec(rt);
        if (!m || !USERS[m[2]]) return json(res, 400, { error: "invalid_grant", error_description: "refresh token invalid" });
        return json(res, 200, issueTokens(USERS[m[2]], form.get("client_id")));
      }
      if (grant === "password") {
        const user = USERS[(form.get("username") || "").trim()];
        if (!user || user.password !== form.get("password"))
          return json(res, 401, { error: "invalid_grant", error_description: "invalid credentials" });
        return json(res, 200, issueTokens(user, form.get("client_id")));
      }
      return json(res, 400, { error: "unsupported_grant_type" });
    });
    return;
  }

  res.writeHead(404, { "Content-Type": "text/plain" });
  res.end("not found");
});

// refresh token format: rt_<hex>_<username> — adjust issuer to match
server.listen(PORT, "127.0.0.1", () => {
  console.log(`[hsaai-demo-idp] listening on http://127.0.0.1:${PORT}`);
  console.log(`[hsaai-demo-idp] issuer: ${ISSUER}`);
  console.log(`[hsaai-demo-idp] kid: ${KEYS.kid}`);
});
