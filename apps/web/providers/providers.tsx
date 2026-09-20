"use client";
import { ThemeProvider } from "next-themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AuthProvider } from "@/lib/auth-provider";
import "@/lib/i18n";

/**
 * SECURITY FIX v2.0:
 *   - Added <AuthProvider> wrapper (was missing — entire client-side auth system was dead code).
 *   - Added default QueryClient options (staleTime, retry, gcTime).
 *
 * UI REDESIGN:
 *   - defaultTheme switched from "system" to "light": the HSAAI identity is
 *     light-first enterprise (index.html reference). Dark mode stays available
 *     via the header toggle.
 *   - i18n (react-i18next) is now initialized here so the language switcher
 *     and RTL/LTR direction switching work across the shell.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000, // 30s
            retry: 2,
            gcTime: 5 * 60_000, // 5min
            refetchOnWindowFocus: false,
          },
        },
      })
  );
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
        <AuthProvider>{children}</AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
