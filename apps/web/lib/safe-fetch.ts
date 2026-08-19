/**
 * HSAAI Enterprise API Client — Safe Fetch Utility v3.0
 * ═══════════════════════════════════════════════════════════════════════
 *
 * CRITICAL FIX (V3): This module replaces ALL ad-hoc fetch() wrappers
 * that used `throw new Error(await response.text())` — which captured
 * entire HTML pages (DOCTYPE + Next.js chunks) as error messages and
 * rendered them verbatim in the UI.
 *
 * This utility guarantees:
 *   1. NEVER uses response.text() as an error message
 *   2. Validates Content-Type is application/json before parsing
 *   3. Returns structured ApiError objects, not raw Error strings
 *   4. Handles all HTTP status codes with friendly Arabic messages
 *   5. Handles network errors, timeouts, and HTML responses gracefully
 *   6. Generates Request-ID for traceability
 *   7. Supports retry with exponential backoff
 *
 * Usage:
 *   import { safeFetch, apiGet, apiPost, apiPut, apiDelete } from "@/lib/safe-fetch";
 *
 *   const data = await apiGet<MyType>("/api/knowledge-graph/health");
 *   if (data.error) { showError(data.error); return; }
 *   console.log(data.data);
 *
 * ═══════════════════════════════════════════════════════════════════════
 */

// ─── Types ──────────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T | null;
  error: ApiError | null;
  status: number;
  requestId: string;
}

export interface ApiError {
  code: string;
  message: string;        // User-friendly Arabic message
  detail?: string;        // Technical detail (for logs, not UI)
  status: number;
  requestId: string;
}

// ─── Error Codes ────────────────────────────────────────────────────────

export const ErrorCodes = {
  NETWORK_ERROR: "NETWORK_ERROR",
  TIMEOUT: "TIMEOUT",
  UNAUTHORIZED: "UNAUTHORIZED",
  FORBIDDEN: "FORBIDDEN",
  NOT_FOUND: "NOT_FOUND",
  RATE_LIMITED: "RATE_LIMITED",
  SERVER_ERROR: "SERVER_ERROR",
  BAD_GATEWAY: "BAD_GATEWAY",
  SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
  GATEWAY_TIMEOUT: "GATEWAY_TIMEOUT",
  INVALID_JSON: "INVALID_JSON",
  HTML_RESPONSE: "HTML_RESPONSE",
  UNKNOWN: "UNKNOWN",
} as const;

// ─── Arabic Error Messages ──────────────────────────────────────────────

const ERROR_MESSAGES: Record<string, string> = {
  [ErrorCodes.NETWORK_ERROR]: "تعذر الاتصال بالخادم. تحقق من اتصال الإنترنت.",
  [ErrorCodes.TIMEOUT]: "انتهت مهلة الطلب. حاول مرة أخرى.",
  [ErrorCodes.UNAUTHORIZED]: "انتهت الجلسة. يرجى تسجيل الدخول مرة أخرى.",
  [ErrorCodes.FORBIDDEN]: "ليس لديك صلاحية للوصول إلى هذا المورد.",
  [ErrorCodes.NOT_FOUND]: "المورد المطلوب غير موجود.",
  [ErrorCodes.RATE_LIMITED]: "تم تجاوز حد الطلبات. حاول لاحقاً.",
  [ErrorCodes.SERVER_ERROR]: "حدث خطأ في الخادم. فريق الدعم تم إبلاغه.",
  [ErrorCodes.BAD_GATEWAY]: "الخادم البعيد غير متاح. حاول لاحقاً.",
  [ErrorCodes.SERVICE_UNAVAILABLE]: "الخدمة غير متاحة حالياً. حاول لاحقاً.",
  [ErrorCodes.GATEWAY_TIMEOUT]: "لم يستجب الخادم في الوقت المحدد.",
  [ErrorCodes.INVALID_JSON]: "استجابة غير صالحة من الخادم (ليست JSON).",
  [ErrorCodes.HTML_RESPONSE]: "استجابة غير صالحة من الخادم (HTML بدلاً من JSON).",
  [ErrorCodes.UNKNOWN]: "حدث خطأ غير متوقع.",
};

// ─── Helper: Generate Request ID ────────────────────────────────────────

function generateRequestId(): string {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).substring(2, 10);
  return `req_${ts}_${rand}`;
}

// ─── Helper: Map HTTP Status to Error Code ──────────────────────────────

function statusToErrorCode(status: number): string {
  if (status === 401) return ErrorCodes.UNAUTHORIZED;
  if (status === 403) return ErrorCodes.FORBIDDEN;
  if (status === 404) return ErrorCodes.NOT_FOUND;
  if (status === 429) return ErrorCodes.RATE_LIMITED;
  if (status >= 500 && status < 502) return ErrorCodes.SERVER_ERROR;
  if (status === 502) return ErrorCodes.BAD_GATEWAY;
  if (status === 503) return ErrorCodes.SERVICE_UNAVAILABLE;
  if (status === 504) return ErrorCodes.GATEWAY_TIMEOUT;
  if (status >= 500) return ErrorCodes.SERVER_ERROR;
  return ErrorCodes.UNKNOWN;
}

// ─── Helper: Create ApiError ────────────────────────────────────────────

function createApiError(
  code: string,
  status: number,
  requestId: string,
  detail?: string
): ApiError {
  return {
    code,
    message: ERROR_MESSAGES[code] || ERROR_MESSAGES[ErrorCodes.UNKNOWN],
    detail,
    status,
    requestId,
  };
}

// ─── Core: safeFetch ────────────────────────────────────────────────────

export interface SafeFetchOptions extends RequestInit {
  timeout?: number;        // milliseconds (default: 15000)
  retries?: number;        // number of retries (default: 1, only for 5xx + network)
  retryDelay?: number;     // base retry delay in ms (default: 500, exponential)
}

export async function safeFetch<T>(
  url: string,
  options: SafeFetchOptions = {}
): Promise<ApiResponse<T>> {
  const requestId = generateRequestId();
  const { timeout = 15000, retries = 1, retryDelay = 500, ...fetchOptions } = options;

  // Build headers — always request JSON
  fetchOptions.headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "X-Request-ID": requestId,
    ...(fetchOptions.headers || {}),
  };

  // Include credentials (cookies) by default
  fetchOptions.credentials = fetchOptions.credentials || "include";

  let lastError: ApiError | null = null;
  let attempts = 0;

  while (attempts <= retries) {
    attempts++;

    try {
      // Timeout via AbortController
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // ─── Check Content-Type ────────────────────────────────────────
      const contentType = response.headers.get("content-type") || "";

      // If response is not OK, extract error safely
      if (!response.ok) {
        let detail: string | undefined;

        // Only try to parse JSON error details — NEVER use text() as the message
        if (contentType.includes("application/json")) {
          try {
            const errorBody = await response.json();
            detail = errorBody?.detail || errorBody?.message || errorBody?.error;
          } catch {
            // JSON parse failed — ignore
          }
        }
        // If HTML response, do NOT read the body — just note it was HTML
        if (contentType.includes("text/html")) {
          detail = `Server returned HTML instead of JSON (status ${response.status})`;
        }

        const errorCode = statusToErrorCode(response.status);
        lastError = createApiError(errorCode, response.status, requestId, detail);

        // Retry only on 5xx errors
        if (response.status >= 500 && attempts <= retries) {
          await new Promise((r) => setTimeout(r, retryDelay * attempts));
          continue;
        }

        return { data: null, error: lastError, status: response.status, requestId };
      }

      // ─── Validate Content-Type is JSON ─────────────────────────────
      if (!contentType.includes("application/json")) {
        // Server returned 200 OK but with HTML (e.g., a redirect page)
        const errorCode = contentType.includes("text/html")
          ? ErrorCodes.HTML_RESPONSE
          : ErrorCodes.INVALID_JSON;
        lastError = createApiError(errorCode, response.status, requestId, `Content-Type: ${contentType}`);
        return { data: null, error: lastError, status: response.status, requestId };
      }

      // ─── Parse JSON safely ─────────────────────────────────────────
      let data: T;
      try {
        data = await response.json();
      } catch (parseError) {
        lastError = createApiError(
          ErrorCodes.INVALID_JSON,
          response.status,
          requestId,
          `JSON.parse failed: ${parseError instanceof Error ? parseError.message : "unknown"}`
        );
        return { data: null, error: lastError, status: response.status, requestId };
      }

      return { data, error: null, status: response.status, requestId };
    } catch (err) {
      // ─── Network errors, timeouts, abort ───────────────────────────
      if (err instanceof DOMException && err.name === "AbortError") {
        lastError = createApiError(ErrorCodes.TIMEOUT, 0, requestId, "Request timed out");
      } else if (err instanceof TypeError && err.message.includes("fetch")) {
        lastError = createApiError(ErrorCodes.NETWORK_ERROR, 0, requestId, err.message);
      } else {
        lastError = createApiError(
          ErrorCodes.UNKNOWN,
          0,
          requestId,
          err instanceof Error ? err.message : String(err)
        );
      }

      // Retry on network errors
      if (attempts <= retries) {
        await new Promise((r) => setTimeout(r, retryDelay * attempts));
        continue;
      }
    }
  }

  return { data: null, error: lastError, status: 0, requestId };
}

// ─── Convenience Methods ────────────────────────────────────────────────

export async function apiGet<T>(url: string, options?: SafeFetchOptions): Promise<ApiResponse<T>> {
  return safeFetch<T>(url, { ...options, method: "GET" });
}

export async function apiPost<T>(url: string, body?: unknown, options?: SafeFetchOptions): Promise<ApiResponse<T>> {
  return safeFetch<T>(url, {
    ...options,
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export async function apiPut<T>(url: string, body?: unknown, options?: SafeFetchOptions): Promise<ApiResponse<T>> {
  return safeFetch<T>(url, {
    ...options,
    method: "PUT",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export async function apiPatch<T>(url: string, body?: unknown, options?: SafeFetchOptions): Promise<ApiResponse<T>> {
  return safeFetch<T>(url, {
    ...options,
    method: "PATCH",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export async function apiDelete<T>(url: string, options?: SafeFetchOptions): Promise<ApiResponse<T>> {
  return safeFetch<T>(url, { ...options, method: "DELETE" });
}

// ─── React Hook: useApi ─────────────────────────────────────────────────

import { useEffect, useState, useCallback } from "react";

export interface UseApiState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  refetch: () => void;
}

export function useApi<T>(
  url: string | null,
  options?: SafeFetchOptions
): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  const refetch = useCallback(() => setRefetchTrigger((n) => n + 1), []);

  useEffect(() => {
    if (!url) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiGet<T>(url, options)
      .then((result) => {
        if (cancelled) return;
        setData(result.data);
        setError(result.error);
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setError(createApiError(ErrorCodes.UNKNOWN, 0, "hook", "useApi catch"));
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, [url, refetchTrigger]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, error, loading, refetch };
}
