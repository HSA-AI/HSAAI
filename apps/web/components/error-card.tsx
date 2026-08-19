/**
 * HSAAI Enterprise Error Card Component
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Professional error display component that NEVER renders raw HTML.
 * Replaces all ad-hoc error divs that used `{error}` interpolation.
 *
 * Features:
 *   - Displays user-friendly Arabic message (never raw HTML)
 *   - Shows error code + request ID for support
 *   - Retry button for transient errors
 *   - Variant: inline (default) | full-page | banner
 *   - WCAG 2.2 AAA compliant
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import type { ApiError } from "@/lib/safe-fetch";

export interface ErrorCardProps extends React.HTMLAttributes<HTMLDivElement> {
  error: ApiError | string | null;
  onRetry?: () => void;
  variant?: "inline" | "full-page" | "banner";
  title?: string;
}

export const ErrorCard = forwardRef<HTMLDivElement, ErrorCardProps>(
  ({ error, onRetry, variant = "inline", title, className, ...props }, ref) => {
    if (!error) return null;

    // Normalize error to ApiError shape
    const apiError: ApiError = typeof error === "string"
      ? {
          code: "UNKNOWN",
          message: error.length > 200 ? error.slice(0, 200) + "…" : error,
          status: 0,
          requestId: "n/a",
        }
      : error;

    // Truncate any message to max 300 chars (defense in depth — never render HTML)
    const safeMessage = apiError.message.length > 300
      ? apiError.message.slice(0, 300) + "…"
      : apiError.message;

    const variantClasses = {
      "inline": "rounded-2xl border border-danger-border bg-danger-soft p-5",
      "full-page": "min-h-[60vh] flex items-center justify-center p-6",
      "banner": "rounded-xl border border-danger-border bg-danger-soft p-3",
    };

    const iconMap: Record<string, string> = {
      NETWORK_ERROR: "📡",
      TIMEOUT: "⏱️",
      UNAUTHORIZED: "🔐",
      FORBIDDEN: "🚫",
      NOT_FOUND: "🔍",
      RATE_LIMITED: "⏳",
      SERVER_ERROR: "⚠️",
      BAD_GATEWAY: "🚪",
      SERVICE_UNAVAILABLE: "🔧",
      GATEWAY_TIMEOUT: "⏰",
      INVALID_JSON: "📋",
      HTML_RESPONSE: "📄",
      UNKNOWN: "❓",
    };

    const icon = iconMap[apiError.code] || "⚠️";
    const canRetry = onRetry && (
      apiError.code === "NETWORK_ERROR" ||
      apiError.code === "TIMEOUT" ||
      apiError.code === "SERVER_ERROR" ||
      apiError.code === "BAD_GATEWAY" ||
      apiError.code === "SERVICE_UNAVAILABLE" ||
      apiError.code === "GATEWAY_TIMEOUT"
    );

    if (variant === "full-page") {
      return (
        <div
          ref={ref}
          className={cn("flex flex-col items-center text-center max-w-md", className)}
          role="alert"
          aria-live="assertive"
          {...props}
        >
          <div className="text-6xl mb-4" aria-hidden="true">{icon}</div>
          <h2 className="text-h2 font-bold text-text-primary mb-2">
            {title || "حدث خطأ"}
          </h2>
          <p className="text-body text-text-secondary mb-6 leading-relaxed">
            {safeMessage}
          </p>
          {canRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center justify-center gap-2 h-10 px-4 text-button font-semibold rounded-xl bg-primary-gold text-primary-black hover:bg-primary-gold-hover active:bg-primary-gold-active transition-all duration-fast shadow-sm hover:shadow-md"
            >
              <span aria-hidden="true">↻</span>
              إعادة المحاولة
            </button>
          )}
          {apiError.requestId && apiError.requestId !== "n/a" && (
            <p className="mt-6 text-caption text-text-muted font-mono">
              Request ID: {apiError.requestId}
            </p>
          )}
        </div>
      );
    }

    return (
      <div
        ref={ref}
        className={cn(variantClasses[variant], className)}
        role="alert"
        aria-live="assertive"
        {...props}
      >
        <div className="flex items-start gap-3">
          <span className="text-2xl flex-shrink-0" aria-hidden="true">{icon}</span>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-danger text-body-sm">
              {title || "حدث خطأ"}
            </p>
            <p className="mt-1 text-body-sm text-danger/80 leading-relaxed">
              {safeMessage}
            </p>
            {apiError.requestId && apiError.requestId !== "n/a" && (
              <p className="mt-2 text-caption text-danger/50 font-mono">
                {apiError.code} · Request ID: {apiError.requestId}
              </p>
            )}
            {canRetry && (
              <button
                onClick={onRetry}
                className="mt-3 inline-flex items-center gap-1.5 h-8 px-3 text-caption font-semibold rounded-lg bg-danger text-white hover:bg-danger/90 transition-colors duration-fast"
              >
                <span aria-hidden="true">↻</span>
                إعادة المحاولة
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }
);

ErrorCard.displayName = "ErrorCard";
