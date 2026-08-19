"use client";

/**
 * FIX v2.1 (P0): Global error.tsx — catches unhandled errors in Server Components.
 * Previously there was no error.tsx, so any unhandled error crashed the whole route.
 *
 * FIX-MEDIUM-LOW-FINAL: Replaced raw `console.error` with structured client-side
 * error reporting. In production we emit a structured JSON log (Next.js captures
 * stdout/stderr from the browser via the OTEL trace context when configured) and
 * forward to a future Sentry/OTEL sink via `window.__hsaaiReportError__` if wired.
 * In development we still print to console for DX.
 */
import { useEffect } from "react";

type StructuredErrorEvent = {
  level: "error";
  message: string;
  digest?: string;
  name: string;
  stack?: string;
  timestamp: string;
  userAgent: string;
  href: string;
};

function reportRouteError(error: Error & { digest?: string }) {
  const isProd = process.env.NODE_ENV === "production";
  const event: StructuredErrorEvent = {
    level: "error",
    message: error.message || "Route error",
    digest: error.digest,
    name: error.name,
    stack: isProd ? undefined : error.stack,
    timestamp: new Date().toISOString(),
    userAgent: typeof navigator !== "undefined" ? navigator.userAgent : "unknown",
    href: typeof window !== "undefined" ? window.location.href : "",
  };

  if (!isProd) {
    // Dev: keep console.error for developer visibility.
    // eslint-disable-next-line no-console
    console.error("Route error:", error);
    return;
  }

  // Prod: structured JSON log (captured by Next.js / OTLP exporter when configured).
  // eslint-disable-next-line no-console
  console.error(JSON.stringify(event));

  // Hook for future Sentry/OTEL integration without hard dependency.
  if (typeof window !== "undefined" && typeof (window as any).__hsaaiReportError__ === "function") {
    try {
      (window as any).__hsaaiReportError__(event);
    } catch {
      // Reporting hook must never throw into the error boundary.
    }
  }
}

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportRouteError(error);
  }, [error]);

  return (
    <div
      role="alert"
      className="min-h-[60vh] flex items-center justify-center p-6"
    >
      <div className="max-w-md w-full space-y-4 text-center">
        <div className="text-6xl">⚠️</div>
        <h2 className="text-xl font-bold text-slate-900">
          حدث خطأ غير متوقع
        </h2>
        <p className="text-sm text-slate-600">
          نعتذر عن الإزعاج. يرجى المحاولة مرة أخرى، أو التواصل مع الدعم الفني
          إذا استمرت المشكلة.
        </p>
        {error.digest && (
          <p className="text-xs text-slate-400">
            معرّف الخطأ: <code className="font-mono">{error.digest}</code>
          </p>
        )}
        <button
          onClick={reset}
          className="px-4 py-2 bg-slate-900 text-white rounded-md hover:bg-slate-800 transition-colors"
        >
          إعادة المحاولة
        </button>
      </div>
    </div>
  );
}
