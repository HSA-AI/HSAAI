/**
 * HSAAI Auth Provider
 *
 * Keycloak OIDC Authorization Code Flow + PKCE
 *
 * Security:
 * - Authorization Code Flow with PKCE
 * - Server-generated PKCE verifier and state
 * - httpOnly cookies for session tokens
 * - No localStorage token storage
 * - Server-side session verification
 * - Automatic session refresh
 * - Logout support
 * - Secure OIDC configuration resolution
 */

"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

/* ============================================================
   TYPES
============================================================ */

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
  userinfo_endpoint?: string;
  end_session_endpoint: string;
  jwks_uri: string;
  realm: string;
  client_id: string;
  audience?: string;
  scopes: string[];
  pkce_enabled: boolean;
  code_challenge_method: string;
}

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  login: () => void;

  loginWithPassword: (
    username: string,
    password: string
  ) => Promise<void>;

  logout: () => Promise<void>;

  refreshToken: () => Promise<void>;

  config: KeycloakConfig | null;
}

/* ============================================================
   CONFIGURATION
============================================================ */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "";

const SESSION_REFRESH_INTERVAL = 840 * 1000;

/* ============================================================
   AUTH CONTEXT
============================================================ */

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

/* ============================================================
   HELPERS
============================================================ */

function validateAuthorizationEndpoint(
  endpoint: string
): URL {
  const url = new URL(endpoint);

  const isHTTPS = url.protocol === "https:";

  const isLocalHTTP =
    url.protocol === "http:" &&
    (
      url.hostname === "localhost" ||
      url.hostname === "127.0.0.1"
    );

  if (!isHTTPS && !isLocalHTTP) {
    throw new Error(
      "OIDC authorization endpoint must use HTTPS"
    );
  }

  if (url.username || url.password) {
    throw new Error(
      "OIDC endpoint must not contain credentials"
    );
  }

  return url;
}

async function fetchOIDCConfig(): Promise<KeycloakConfig> {
  const response = await fetch(
    `${API_BASE}/v1/keycloak/config`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      `OIDC configuration request failed: ${response.status}`
    );
  }

  const data =
    (await response.json()) as KeycloakConfig;

  if (
    !data ||
    !data.issuer ||
    !data.authorization_endpoint ||
    !data.client_id
  ) {
    throw new Error(
      "Invalid OIDC configuration"
    );
  }

  validateAuthorizationEndpoint(
    data.authorization_endpoint
  );

  return data;
}

/* ============================================================
   AUTH PROVIDER
============================================================ */

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] =
    useState<AuthUser | null>(null);

  const [isLoading, setIsLoading] =
    useState(true);

  const [config, setConfig] =
    useState<KeycloakConfig | null>(null);

  const refreshTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null
    );

  /* ==========================================================
     INITIALIZATION
  ========================================================== */

  useEffect(() => {
    void loadConfig();
    void checkSession();

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };

    // Initialize browser session once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ==========================================================
     LOAD KEYCLOAK CONFIG
  ========================================================== */

  async function loadConfig() {
    try {
      const oidcConfig =
        await fetchOIDCConfig();

      setConfig(oidcConfig);
    } catch (error) {
      console.error(
        "HSAAI OIDC configuration error:",
        error
      );

      // No unsafe fallback to localhost:8080.
      setConfig(null);
    }
  }

  /* ==========================================================
     CHECK SESSION
  ========================================================== */

  async function checkSession() {
    try {
      const response = await fetch(
        `${API_BASE}/v1/auth/me`,
        {
          method: "GET",
          credentials: "include",
          signal: AbortSignal.timeout(8000),
        }
      );

      if (response.ok) {
        const data = await response.json();

        setUser({
          sub: data.sub,
          roles: data.roles || ["ai_user"],
          tenant_id:
            data.tenant_id || "default",
          workspace_id:
            data.workspace_id || "default",
          email: data.email,
          username: data.username,
          preferred_username:
            data.preferred_username,
        });

        scheduleRefresh();
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }

  /* ==========================================================
     TOKEN REFRESH SCHEDULER
  ========================================================== */

  function scheduleRefresh() {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }

    refreshTimerRef.current = setTimeout(
      () => {
        void refreshToken();
      },
      SESSION_REFRESH_INTERVAL
    );
  }

  /* ==========================================================
     LOGIN — OIDC + PKCE
  ========================================================== */

  async function login() {
    try {
      /*
       * Step 1:
       * Ensure OIDC configuration is available.
       */

      let authConfig = config;

      if (!authConfig?.authorization_endpoint) {
        authConfig = await fetchOIDCConfig();

        setConfig(authConfig);
      }

      /*
       * Step 2:
       * Validate authorization endpoint.
       */

      const authorizationUrl =
        validateAuthorizationEndpoint(
          authConfig.authorization_endpoint
        );

      /*
       * Step 3:
       * Preserve requested return route.
       */

      const returnTo =
        window.location.pathname +
        window.location.search;

      /*
       * Step 4:
       * Initialize PKCE on the server.
       */

      const startResponse = await fetch(
        "/api/auth/start",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            returnTo,
          }),
        }
      );

      if (!startResponse.ok) {
        throw new Error(
          `PKCE initialization failed: ${startResponse.status}`
        );
      }

      const {
        codeChallenge,
        codeChallengeMethod,
        state,
      } = await startResponse.json();

      if (
        !codeChallenge ||
        !state ||
        codeChallengeMethod !== "S256"
      ) {
        throw new Error(
          "Invalid PKCE initialization response"
        );
      }

      /*
       * Step 5:
       * Build callback URL.
       */

      const redirectUri =
        `${window.location.origin}/api/auth/callback`;

      /*
       * Step 6:
       * Build OIDC authorization request.
       */

      const params = new URLSearchParams({
        client_id: authConfig.client_id,
        redirect_uri: redirectUri,
        response_type: "code",
        scope:
          "openid profile email roles",
        code_challenge: codeChallenge,
        code_challenge_method:
          codeChallengeMethod,
        state,
      });

      /*
       * Step 7:
       * Redirect to configured Keycloak.
       */

      authorizationUrl.search =
        params.toString();

      window.location.assign(
        authorizationUrl.toString()
      );
    } catch (error) {
      console.error(
        "HSAAI OIDC login failed:",
        error
      );

      window.alert(
        "تعذر بدء تسجيل الدخول. تحقق من اتصال المنصة بخادم المصادقة."
      );
    }
  }

  /* ==========================================================
     PASSWORD LOGIN
  ========================================================== */

  async function loginWithPassword(
    username: string,
    password: string
  ) {
    const response = await fetch(
      `${API_BASE}/v1/auth/login`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          username,
          password,
        }),
      }
    );

    if (!response.ok) {
      const error =
        await response.json().catch(
          () => ({})
        );

      throw new Error(
        error.detail || "Login failed"
      );
    }

    const data = await response.json();

    setUser(data.user);

    scheduleRefresh();
  }

  /* ==========================================================
     LOGOUT
  ========================================================== */

  async function logout() {
    try {
      await fetch(
        `${API_BASE}/v1/auth/logout`,
        {
          method: "POST",
          headers: {
            "X-Requested-With":
              "XMLHttpRequest",
          },
          credentials: "include",
        }
      );
    } catch (error) {
      console.error(
        "HSAAI logout request failed:",
        error
      );
    }

    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    setUser(null);

    if (config?.end_session_endpoint) {
      try {
        const logoutUrl =
          validateAuthorizationEndpoint(
            config.end_session_endpoint
          );

        window.location.assign(
          logoutUrl.toString()
        );

        return;
      } catch (error) {
        console.error(
          "Invalid logout endpoint:",
          error
        );
      }
    }
  }

  /* ==========================================================
     REFRESH SESSION
  ========================================================== */

  async function refreshToken() {
    try {
      const response = await fetch(
        `${API_BASE}/v1/auth/refresh`,
        {
          method: "POST",
          headers: {
            "X-Requested-With":
              "XMLHttpRequest",
          },
          credentials: "include",
        }
      );

      if (response.ok) {
        const data = await response.json();

        setUser(data.user);

        scheduleRefresh();
      } else {
        setUser(null);

        if (refreshTimerRef.current) {
          clearTimeout(
            refreshTimerRef.current
          );

          refreshTimerRef.current = null;
        }
      }
    } catch (error) {
      console.error(
        "HSAAI token refresh failed:",
        error
      );

      setUser(null);
    }
  }

  /* ==========================================================
     CONTEXT PROVIDER
  ========================================================== */

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

/* ============================================================
   AUTH HOOKS
============================================================ */

export function useAuth() {
  return useContext(AuthContext);
}

export function useRoles(): string[] {
  const { user } = useAuth();

  return user?.roles || ["viewer"];
}

/* ============================================================
   SERVER-SIDE TOKEN EXCHANGE

   Compatibility note:
   This function is preserved from the original file.
   It should be moved to a server-only module before
   production deployment.
============================================================ */
