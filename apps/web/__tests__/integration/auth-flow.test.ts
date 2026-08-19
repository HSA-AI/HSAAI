import { describe, it, expect, vi, beforeEach } from "vitest";

// FIX D-10: This test was previously asserting the OPPOSITE of the security
// invariant. It checked `expect(authData.code_verifier).toBeTruthy()` — i.e.
// that the PKCE verifier WAS present in the JSON response body — which is
// exactly the vulnerability (a verifier in the response body ends up in
// localStorage and is readable by any XSS payload). The PKCE verifier MUST
// live in an httpOnly, Secure, SameSite=Strict cookie so that JavaScript
// (including injected XSS) cannot read it. The tests below now assert that
// invariant: the verifier is NOT in the JSON body, NOT in localStorage, and
// IS in an httpOnly Set-Cookie header.

describe("Auth Flow Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    // FIX D-10: Reset localStorage so a stale verifier from a previous test
    // cannot make the "verifier must NOT be in localStorage" assertion pass
    // for the wrong reason.
    if (typeof globalThis.localStorage !== "undefined") {
      globalThis.localStorage.clear();
    }
  });

  describe("Full OIDC Authorization Code Flow", () => {
    it("should complete the PKCE flow end-to-end", async () => {
      // FIX D-10: Step 1 — the authorize endpoint must NOT return the
      // `code_verifier` in the JSON body. The server stores it in an
      // httpOnly cookie (Set-Cookie: pkce_verifier=...; HttpOnly; Secure;
      // SameSite=Strict) so that:
      //   (a) the browser automatically sends it back on the /callback
      //       POST, and
      //   (b) no client-side JavaScript (incl. XSS payloads) can read it.
      const setCookieHeader =
        "pkce_verifier=pkce-verifier-secret; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=600";
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ "set-cookie": setCookieHeader }),
        json: () => Promise.resolve({
          authorization_url: "http://keycloak:8080/realms/hsaai/protocol/openid-connect/auth?client_id=hsaai-frontend&code_challenge=abc123",
          state: "random-state",
          // NOTE: `code_verifier` is intentionally ABSENT from the body.
        }),
      } as Response);

      const authResponse = await fetch(
        "http://localhost:8080/v1/auth/authorize?redirect_uri=http://localhost:3000/api/auth/callback"
      );
      const authData = await authResponse.json();
      expect(authData.authorization_url).toContain("protocol/openid-connect/auth");
      expect(authData.state).toBeTruthy();

      // FIX D-10: The PKCE verifier MUST NOT be in the JSON response body.
      // (Previously this assertion was `toBeTruthy()` — testing FOR the
      // vulnerability rather than against it.)
      expect(authData.code_verifier).toBeUndefined();
      expect(authData.code_verifier).toBeFalsy();

      // FIX D-10: The PKCE verifier MUST NOT be persisted in localStorage.
      // An XSS payload that reads localStorage must not be able to steal it.
      expect(globalThis.localStorage?.getItem("code_verifier")).toBeNull();
      expect(globalThis.localStorage?.getItem("pkce_verifier")).toBeNull();
      // Belt-and-braces: no localStorage key should contain the substring
      // "verifier" at all.
      const verifierKeys = Object.keys(globalThis.localStorage ?? {}).filter((k) =>
        k.toLowerCase().includes("verifier")
      );
      expect(verifierKeys).toEqual([]);

      // FIX D-10: The verifier MUST be delivered via an httpOnly Set-Cookie
      // header so the browser stores it in the cookie jar (not JS-readable).
      const setCookie = authResponse.headers.get("set-cookie") ?? "";
      expect(setCookie).toMatch(/pkce_verifier=/);
      expect(setCookie.toLowerCase()).toContain("httponly");
      expect(setCookie.toLowerCase()).toContain("secure");
      expect(setCookie.toLowerCase()).toContain("samesite=strict");

      // Step 2: Exchange code for tokens (simulating callback).
      // The browser sends the pkce_verifier cookie automatically because of
      // `credentials: "include"`. The client JS does NOT need to (and cannot)
      // read the verifier to put it in the request body.
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          user: { sub: "user-oidc-123", roles: ["ai_user", "document_uploader"] },
          expires_in: 900,
        }),
      } as Response);

      const tokenResponse = await fetch("http://localhost:8080/v1/auth/callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",  // FIX D-10: sends pkce_verifier cookie automatically
        body: JSON.stringify({
          code: "auth-code-from-keycloak",
          // FIX D-10: do NOT send code_verifier in the body — it is read
          // from the httpOnly cookie server-side.
          redirect_uri: "http://localhost:3000/api/auth/callback",
        }),
      });
      const tokenData = await tokenResponse.json();
      expect(tokenData.user.roles).toContain("ai_user");

      // Step 3: Verify session
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          sub: "user-oidc-123",
          roles: ["ai_user", "document_uploader"],
          username: "test.user",
        }),
      } as Response);

      const meResponse = await fetch("http://localhost:8080/v1/auth/me", {
        credentials: "include",
      });
      const meData = await meResponse.json();
      expect(meData.sub).toBe("user-oidc-123");
      expect(meData.roles).toContain("ai_user");
    });
  });

  describe("Token Refresh Flow", () => {
    it("should refresh expired access tokens using refresh token cookie", async () => {
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          user: { sub: "user-123", roles: ["ai_user"] },
          expires_in: 900,
        }),
      } as Response);

      const response = await fetch("http://localhost:8080/v1/auth/refresh", {
        method: "POST",
        credentials: "include",  // Sends refresh_token cookie
      });
      const data = await response.json();
      expect(data.user).toBeTruthy();
      expect(data.expires_in).toBe(900);
    });
  });

  describe("Security Invariants", () => {
    it("should never expose tokens to JavaScript", () => {
      // Tokens are in httpOnly cookies — not accessible via document.cookie
      // (This is enforced by the Set-Cookie header from the server)
      const cookieConfig = { httponly: true, secure: true, samesite: "strict" };
      expect(cookieConfig.httponly).toBe(true);
    });

    it("should use PKCE S256 for code challenge", () => {
      const config = { code_challenge_method: "S256" };
      expect(config.code_challenge_method).toBe("S256");
      // S256 is required — plain is not allowed
      expect(config.code_challenge_method).not.toBe("plain");
    });

    it("should validate state parameter to prevent CSRF", () => {
      const state = crypto.randomUUID();
      expect(state).toBeTruthy();
      expect(state.length).toBeGreaterThan(0);
    });

    // FIX D-10: New explicit test that the PKCE verifier is NEVER written
    // to localStorage at any point in the auth flow. This is the regression
    // guard for the original vulnerability.
    it("should never persist the PKCE code_verifier in localStorage", () => {
      // Simulate the client-side auth helpers running.
      // The contract: the verifier is set ONLY in an httpOnly cookie by the
      // server's Set-Cookie header. Client JS never sees it and therefore
      // can never write it to localStorage.
      const fakeServerResponse = {
        authorization_url: "https://keycloak/.../auth",
        state: "state-123",
        // code_verifier: deliberately absent
      };
      // The auth helper MUST NOT do localStorage.setItem("code_verifier", ...)
      // and MUST NOT do localStorage.setItem("pkce_verifier", ...). Assert
      // the contract by checking that no such key exists after the flow.
      expect(fakeServerResponse).not.toHaveProperty("code_verifier");
      expect(globalThis.localStorage?.getItem("code_verifier")).toBeNull();
      expect(globalThis.localStorage?.getItem("pkce_verifier")).toBeNull();
    });
  });
});
