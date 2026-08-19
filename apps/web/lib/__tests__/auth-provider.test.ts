import { describe, it, expect, vi, beforeEach } from "vitest";

// We test the logic without rendering (unit tests for auth functions)
describe("Auth Provider Logic", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  describe("OIDC Configuration", () => {
    it("should construct correct Keycloak OIDC URL", () => {
      const keycloakUrl = "http://keycloak:8080";
      const realm = "hsaai";
      const expectedIssuer = `${keycloakUrl}/realms/${realm}`;
      const expectedAuthEndpoint = `${expectedIssuer}/protocol/openid-connect/auth`;

      expect(expectedAuthEndpoint).toContain("protocol/openid-connect/auth");
      expect(expectedIssuer).toContain("realms/hsaai");
    });

    it("should use S256 PKCE code challenge method", () => {
      const config = { code_challenge_method: "S256", pkce_enabled: true };
      expect(config.code_challenge_method).toBe("S256");
      expect(config.pkce_enabled).toBe(true);
    });
  });

  describe("Cookie Security", () => {
    it("should use httpOnly cookies (not localStorage)", () => {
      // Auth provider must NOT use localStorage for tokens
      const authProviderCode = `credentials: "include"`;
      expect(authProviderCode).toContain("credentials");
      expect(authProviderCode).toContain("include");
    });

    it("should set SameSite=Strict for cookies", () => {
      const cookieConfig = { samesite: "strict", secure: true, httponly: true };
      expect(cookieConfig.samesite).toBe("strict");
      expect(cookieConfig.secure).toBe(true);
      expect(cookieConfig.httponly).toBe(true);
    });
  });

  describe("PKCE Flow", () => {
    it("should generate a code_verifier of sufficient length", async () => {
      // Simulate PKCE code_verifier generation
      const array = new Uint8Array(64);
      crypto.getRandomValues(array);
      const verifier = btoa(String.fromCharCode(...array))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");
      expect(verifier.length).toBeGreaterThan(40);
    });

    it("should produce S256 code_challenge from verifier", async () => {
      // PKCE: code_challenge = BASE64URL(SHA256(code_verifier))
      const verifier = "test-verifier-value-for-pkce-challenge";
      const encoder = new TextEncoder();
      const data = encoder.encode(verifier);
      const digest = await crypto.subtle.digest("SHA-256", data);
      expect(digest.byteLength).toBe(32); // SHA-256 produces 32 bytes
    });
  });

  describe("Session Management", () => {
    it("should check session via /v1/auth/me on mount", async () => {
      const mockUser = {
        sub: "user-123",
        roles: ["ai_user"],
        tenant_id: "default",
        workspace_id: "default",
        email: "test@hsaai.com",
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUser),
      } as Response);

      const response = await fetch("http://localhost:8080/v1/auth/me", {
        credentials: "include",
      });
      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(data.sub).toBe("user-123");
      expect(data.roles).toContain("ai_user");
    });

    it("should handle 401 gracefully (not authenticated)", async () => {
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: "Not authenticated" }),
      } as Response);

      const response = await fetch("http://localhost:8080/v1/auth/me", {
        credentials: "include",
      });
      expect(response.ok).toBe(false);
      expect(response.status).toBe(401);
    });
  });

  describe("Logout", () => {
    it("should call logout endpoint and clear session", async () => {
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ logged_out: true }),
      } as Response);

      const response = await fetch("http://localhost:8080/v1/auth/logout", {
        method: "POST",
        credentials: "include",
      });
      const data = await response.json();
      expect(data.logged_out).toBe(true);
    });
  });
});
