import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// ── Keycloak OIDC Configuration ──
const KEYCLOAK_CONFIG = {
  issuer: 'http://hsaai.local:8080/realms/hsaai',
  clientId: 'hsaai-mobile',
  redirectUri: 'hsaai://callback',
  scopes: ['openid', 'profile', 'email', 'offline_access'],
};

// Storage keys
const TOKEN_KEY = 'hsaai_access_token';
const REFRESH_TOKEN_KEY = 'hsaai_refresh_token';
const USER_KEY = 'hsaai_user';

export interface HSAAIUser {
  id: string;
  username: string;
  email: string;
  displayName: string;
  roles: string[];
  department?: string;
}

// ── Token storage (secure on native, AsyncStorage fallback) ──
async function secureSet(key: string, value: string): Promise<void> {
  if (Platform.OS === 'web') {
    localStorage.setItem(key, value);
  } else {
    await SecureStore.setItemAsync(key, value);
  }
}

async function secureGet(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    return localStorage.getItem(key);
  }
  return await SecureStore.getItemAsync(key);
}

async function secureDelete(key: string): Promise<void> {
  if (Platform.OS === 'web') {
    localStorage.removeItem(key);
  } else {
    await SecureStore.deleteItemAsync(key);
  }
}

// ── Auth functions ──
export async function getAuthToken(): Promise<string | null> {
  return secureGet(TOKEN_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return secureGet(REFRESH_TOKEN_KEY);
}

export async function getCurrentUser(): Promise<HSAAIUser | null> {
  const userStr = await secureGet(USER_KEY);
  if (userStr) {
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
  return null;
}

export async function setAuthSession(
  accessToken: string,
  refreshToken: string,
  user: HSAAIUser,
): Promise<void> {
  await secureSet(TOKEN_KEY, accessToken);
  await secureSet(REFRESH_TOKEN_KEY, refreshToken);
  await secureSet(USER_KEY, JSON.stringify(user));
}

export async function refreshAuthToken(): Promise<string | null> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${KEYCLOAK_CONFIG.issuer}/protocol/openid-connect/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: KEYCLOAK_CONFIG.clientId,
        refresh_token: refreshToken,
      }),
    });

    if (!response.ok) throw new Error('Token refresh failed');

    const data = await response.json();
    await secureSet(TOKEN_KEY, data.access_token);
    if (data.refresh_token) {
      await secureSet(REFRESH_TOKEN_KEY, data.refresh_token);
    }
    return data.access_token;
  } catch (error) {
    await clearAuth();
    return null;
  }
}

export async function clearAuth(): Promise<void> {
  await secureDelete(TOKEN_KEY);
  await secureDelete(REFRESH_TOKEN_KEY);
  await secureDelete(USER_KEY);
}

export async function isAuthenticated(): Promise<boolean> {
  const token = await getAuthToken();
  return token !== null;
}

// ── Login with username/password (Resource Owner Password Grant) ──
export async function loginWithPassword(
  username: string,
  password: string,
): Promise<HSAAIUser> {
  const response = await fetch(`${KEYCLOAK_CONFIG.issuer}/protocol/openid-connect/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'password',
      client_id: KEYCLOAK_CONFIG.clientId,
      username,
      password,
      scope: KEYCLOAK_CONFIG.scopes.join(' '),
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error_description || 'فشل تسجيل الدخول');
  }

  const tokens = await response.json();

  // Decode JWT to get user info
  const user = decodeJwtUser(tokens.access_token);
  await setAuthSession(tokens.access_token, tokens.refresh_token, user);

  return user;
}

// ── Decode JWT to extract user info ──
function decodeJwtUser(jwt: string): HSAAIUser {
  const parts = jwt.split('.');
  if (parts.length !== 3) throw new Error('Invalid JWT');

  const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));

  return {
    id: payload.sub,
    username: payload.preferred_username || payload.username || '',
    email: payload.email || '',
    displayName: payload.name || payload.preferred_username || '',
    roles: payload.realm_access?.roles || [],
    department: payload.department,
  };
}

export { KEYCLOAK_CONFIG };
