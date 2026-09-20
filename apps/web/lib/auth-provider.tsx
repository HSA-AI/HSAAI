/**
 * HSAAI Auth Provider — Full Keycloak OIDC Authorization Code Flow + PKCE
 *
 * SECURITY:
 *   - Authorization Code Flow with PKCE (no implicit flow)
 *   - Tokens stored in httpOnly cookies (set by backend, not accessible via JS)
 *   - No localStorage/token exposure to JavaScript
 *   - Server-side session management via /v1/auth/me
 *   - Automatic token refresh before expiry
 *   - Proper logout with back-channel notification
 */
"use client";

import { createContext, useContext, useEffect, useState, useRef, ReactNode } from "react";

export interface AuthUser {
  sub: string;
  roles: string[];
  tenant_id: string;
  workspace_id: string;
  email?: string;
  username?: string;
  preferred_username?: string;  // FIX (runtime): referenced in app/chat/page.tsx
}

interface KeycloakConfig {
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  end_session_endpoint: string;
  jwks_uri: string;
  realm: string;
  client_id: string;
  scopes: string[];
  pkce_enabled: boolean;
  code_challenge_method: string;
}

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: () => void;                    // Redirects to Keycloak
  loginWithPassword: (username: string, password: string) => Promise<void>;  // For non-browser clients
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  config: KeycloakConfig | null;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  login: () => {},
  loginWithPassword: async () => {},
  logout: async () => {},
  refreshToken: async () => {},
  config: null,
});

// FIX (post-audit): fallback was http://localhost:8080 — that is the Keycloak
// port in docker-compose, not the API. server-auth.ts (SSR) falls back to
// :8000; the client must agree with it.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// PKCE helpers
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [config, setConfig] = useState<KeycloakConfig | null>(null);
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load Keycloak OIDC config on mount
  useEffect(() => {
    loadConfig();
    checkSession();
    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  // Initialization reads the current browser session once on mount.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadConfig() {
    try {
      const response = await fetch(`${API_BASE}/v1/keycloak/config`);
      if (response.ok) {
        const cfg = await response.json();
        setConfig(cfg);
      }
    } catch {
      // Config unavailable — will use defaults
    }
  }

  async function checkSession() {
    try {
      const response = await fetch(`${API_BASE}/v1/auth/me`, {
        credentials: "include", // httpOnly cookies sent automatically
      });
      if (response.ok) {
        const data = await response.json();
        setUser({
          sub: data.sub,
          roles: data.roles || ["ai_user"],
          tenant_id: data.tenant_id || "default",
          workspace_id: data.workspace_id || "default",
          email: data.email,
          username: data.username,
        });
        scheduleRefresh();
      }
    } catch {
      // Not authenticated
    } finally {
      setIsLoading(false);
    }
  }

  function scheduleRefresh() {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    // Refresh 60 seconds before token expiry (15 min - 60s = 840s)
    refreshTimerRef.current = setTimeout(() => {
      refreshToken();
    }, 840 * 1000);
  }

  /**
   * OIDC Authorization Code Flow with PKCE:
   * FIX F-04: Use server-side /api/auth/start to store PKCE verifier + state in
   * httpOnly cookies. Previously stored in sessionStorage — callback route reads
   * cookies → state always mismatched → every login failed with state_mismatch.
   */
  async function login() {
    const returnTo = window.location.pathname + window.location.search;
    const startResp = await fetch("/api/auth/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ returnTo }),
    });
    if (!startResp.ok) {
      console.error("Failed to start OIDC flow");
      return;
    }
    const { codeChallenge, codeChallengeMethod, state } = await startResp.json();

    const redirectUri = `${window.location.origin}/api/auth/callback`;
    const params = new URLSearchParams({
      client_id: config?.client_id || "hsaai-frontend",
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "openid profile email roles",
      code_challenge: codeChallenge,
      code_challenge_method: codeChallengeMethod,
      state: state,
    });

    const authEndpoint = config?.authorization_endpoint ||
      `${config?.issuer || "http://localhost:8080/realms/hsaai"}/protocol/openid-connect/auth`;

    window.location.assign(new URL(`${authEndpoint}?${params.toString()}`).toString());
  }

  /**
   * Resource Owner Password Credentials login (for CLI/API clients).
   * Browser clients should use login() which uses PKCE.
   */
  async function loginWithPassword(username: string, password: string) {
    const response = await fetch(`${API_BASE}/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Login failed");
    }
    const data = await response.json();
    setUser(data.user);
    scheduleRefresh();
  }

  async function logout() {
    try {
      await fetch(`${API_BASE}/v1/auth/logout`, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "include",
      });
    } catch {
      // Best-effort logout
    }
    // Also redirect to Keycloak end_session_endpoint for front-channel logout
    if (config?.end_session_endpoint) {
      window.location.href = config.end_session_endpoint;
      return;
    }
    setUser(null);
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
  }

  async function refreshToken() {
    try {
      const response = await fetch(`${API_BASE}/v1/auth/refresh`, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "include",
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
        scheduleRefresh();
      } else {
        // Refresh failed — session expired
        setUser(null);
      }
    } catch {
      setUser(null);
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        loginWithPassword,
        logout,
        refreshToken,
        config,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export function useRoles(): string[] {
  const { user } = useAuth();
  return user?.roles || ["viewer"];
}

/**
 * FIX v2.1 (P0): exchangeCodeForTokens — server-side callable function that
 * exchanges an OIDC authorization code for access/refresh tokens.
 * Used by the /api/auth/callback route handler (Next.js Route Handler).
 *
 * FIX F-04: Now accepts the PKCE code_verifier (read from httpOnly cookie by
 * the caller). Previously did not send code_verifier → PKCE verification failed
 * server-side at Keycloak.
 *
 * This function runs server-side only (in the Next.js server runtime).
 * It performs the back-channel token exchange with Keycloak using PKCE.
 */
export async function exchangeCodeForTokens(
  code: string,
  redirectUri: string,
  codeVerifier: string,
): Promise<{
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_in?: number;
}> {
  const keycloakUrl = process.env.KEYCLOAK_URL || "http://keycloak:8080";
  const realm = process.env.KEYCLOAK_REALM || "hsaai";
  const clientId = process.env.KEYCLOAK_CLIENT_ID || "hsaai-frontend";
  const clientSecret = process.env.KEYCLOAK_CLIENT_SECRET;

  if (!codeVerifier) {
    throw new Error("PKCE code_verifier is missing — cannot complete token exchange");
  }

  const tokenEndpoint = `${keycloakUrl}/realms/${realm}/protocol/openid-connect/token`;

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    code_verifier: codeVerifier,  // FIX F-04: required for PKCE verification
  });
  if (clientSecret) body.set("client_secret", clientSecret);

  const response = await fetch(tokenEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Token exchange failed: ${response.status} ${errorText}`);
  }

  return response.json();
}
