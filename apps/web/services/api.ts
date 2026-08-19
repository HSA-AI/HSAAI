/**
 * HSAAI API Client — httpOnly Cookie Authentication
 *
 * SECURITY: All authentication is handled via httpOnly Secure SameSite=Strict
 * cookies set by the auth service. No tokens are stored in localStorage.
 * The browser automatically sends cookies with credentials: "include".
 */
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,  // Send httpOnly cookies with every request
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor: handle 401 (session expired) → redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Session expired — redirect to login if in browser
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login?reason=session_expired";
      }
    }
    return Promise.reject(error);
  }
);

// Request interceptor: add CSRF double-submit token header
// (The cookie-based auth + SameSite=Strict provides baseline CSRF protection,
//  but we add a custom X-Requested-With header as an extra layer)
api.interceptors.request.use((config) => {
  config.headers["X-Requested-With"] = "XMLHttpRequest";
  return config;
});

export default api;

// Typed API methods
export async function fetchCurrentUser() {
  const response = await api.get("/v1/auth/me");
  return response.data;
}

export async function loginWithPassword(username: string, password: string) {
  const response = await api.post("/v1/auth/login", { username, password });
  return response.data;
}

export async function refreshSession() {
  const response = await api.post("/v1/auth/refresh");
  return response.data;
}

export async function logoutUser() {
  const response = await api.post("/v1/auth/logout");
  return response.data;
}
