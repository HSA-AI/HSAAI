/**
 * HSAAI Auth Provider
 *
 * Security:
 * - Authorization Code Flow with PKCE.
 * - Tokens are handled by the backend using httpOnly cookies.
 * - No access/refresh/id tokens are exposed to browser JavaScript.
 * - Server-side session validation through /v1/auth/me.
 * - Automatic refresh before the expected session expiry.
 */

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export interface AuthUser {
  sub: string;
  roles: string[];
  tenant_id: string;
  workspace_id: string;
  email?: string;
  username?: string;
  preferred_username?: string;
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
  login: () => void;
  loginWithPassword: (username: string, password: string) => Promise<void>;
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

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

const REFRESH_DELAY_MS = 840 * 1000;

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [config, setConfig] = useState<KeycloakConfig | null>(null);

  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  const refreshTokenRef = useRef<() => Promise<void>>(
    async () => {},
  );

  const scheduleRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }

    refreshTimerRef.current = setTimeout(() => {
      void refreshTokenRef.current();
    }, REFRESH_DELAY_MS);
  }, []);

  const loadConfig = useCallback(async () => {
    try {
      const response = await fetch(
        `${API_BASE}/v1/keycloak/config`,
        {
          credentials: "include",
        },
      );

      if (!response.ok) {
        return;
      }

      const cfg: KeycloakConfig = await response.json();
      setConfig(cfg);
    } catch {
      // Keycloak configuration is optional during local startup.
    }
  }, []);

  const checkSession = useCallback(async () => {
    try {
      const response = await fetch(
        `${API_BASE}/v1/auth/me`,
        {
          credentials: "include",
        },
      );

      if (!response.ok) {
        setUser(null);
        return;
      }

      const data = await response.json();

      const authenticatedUser: AuthUser = {
        sub: data.sub,
        roles: data.roles || ["ai_user"],
        tenant_id: data.tenant_id || "default",
        workspace_id: data.workspace_id || "default",
        email: data.email,
        username: data.username,
        preferred_username: data.preferred_username,
      };

      setUser(authenticatedUser);
      scheduleRefresh();
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [scheduleRefresh]);

  const refreshToken = useCallback(async () => {
    try {
      const response = await fetch(
        `${API_BASE}/v1/auth/refresh`,
        {
          method: "POST",
          credentials: "include",
        },
      );

      if (!response.ok) {
        setUser(null);

        if (refreshTimerRef.current) {
          clearTimeout(refreshTimerRef.current);
          refreshTimerRef.current = null;
        }

        return;
      }

      const data = await response.json();

      setUser(data.user);
      scheduleRefresh();
    } catch {
      setUser(null);

      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    }
  }, [scheduleRefresh]);

  refreshTokenRef.current = refreshToken;

  useEffect(() => {
    void loadConfig();
    void checkSession();

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [checkSession, loadConfig]);

  /**
   * OIDC Authorization Code Flow with PKCE.
   *
   * The backend creates and stores the PKCE verifier/state
   * in secure httpOnly cookies through /api/auth/start.
   */
  async function login() {
    const returnTo =
      window.location.pathname + window.location.search;

    const startResponse = await fetch("/api/auth/start", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify({ returnTo }),
    });

    if (!startResponse.ok) {
      console.error("Failed to start OIDC flow");
      return;
    }

    const {
      codeChallenge,
      codeChallengeMethod,
      state,
    } = await startResponse.json();

    const redirectUri =
      `${window.location.origin}/api/auth/callback`;

    const params = new URLSearchParams({
      client_id:
        config?.client_id || "hsaai-frontend",
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "openid profile email roles",
      code_challenge: codeChallenge,
      code_challenge_method: codeChallengeMethod,
      state,
    });

    const authEndpoint =
      config?.authorization_endpoint ||
      `${config?.issuer || "http://keycloak:8080/realms/hsaai"}/protocol/openid-connect/auth`;

    window.location.href =
      `${authEndpoint}?${params.toString()}`;
  }

  /**
   * Resource Owner Password Credentials login.
   *
   * Intended for non-browser clients and controlled
   * internal integrations. Browser authentication should
   * use login() with PKCE.
   */
  async function loginWithPassword(
    username: string,
    password: string,
  ) {
    const response = await fetch(
      `${API_BASE}/v1/auth/login`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          username,
          password,
        }),
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      throw new Error(
        error.detail || "Login failed",
      );
    }

    const data = await response.json();

    setUser(data.user);
    scheduleRefresh();
  }

  async function logout() {
    try {
      await fetch(
        `${API_BASE}/v1/auth/logout`,
        {
          method: "POST",
          credentials: "include",
        },
      );
    } catch {
      // Best-effort backend logout.
    }

    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    setUser(null);

    if (config?.end_session_endpoint) {
      window.location.href =
        config.end_session_endpoint;
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
 * Server-side OIDC authorization-code exchange.
 *
 * This function is intended to be called by the
 * Next.js /api/auth/callback route.
 *
 * The code_verifier is read server-side from the
 * secure httpOnly PKCE cookie.
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
  const keycloakUrl =
    process.env.KEYCLOAK_URL ||
    "http://keycloak:8080";

  const realm =
    process.env.KEYCLOAK_REALM ||
    "hsaai";

  const clientId =
    process.env.KEYCLOAK_CLIENT_ID ||
    "hsaai-frontend";

  const clientSecret =
    process.env.KEYCLOAK_CLIENT_SECRET;

  if (!clientSecret) {
    throw new Error(
      "KEYCLOAK_CLIENT_SECRET is not set — cannot exchange code for tokens",
    );
  }

  if (!codeVerifier) {
    throw new Error(
      "PKCE code_verifier is missing — cannot complete token exchange",
    );
  }

  const tokenEndpoint =
    `${keycloakUrl}/realms/${realm}/protocol/openid-connect/token`;

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    client_secret: clientSecret,
    code_verifier: codeVerifier,
  });

  const response = await fetch(
    tokenEndpoint,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/x-www-form-urlencoded",
      },
      body,
    },
  );

  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      `Token exchange failed: ${response.status} ${errorText}`,
    );
  }

  return response.json();
}
