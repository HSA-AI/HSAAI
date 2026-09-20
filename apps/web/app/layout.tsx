import type { Metadata, Viewport } from "next";
import "../styles/globals.css";
import { Providers } from "@/providers/providers";
import { FloatingAssistant } from "@/components/assistant/floating-assistant";
import { RegisterServiceWorker } from "@/components/pwa/register-service-worker";

export const metadata: Metadata = {
  title: "HSAAI | منصة التشغيل الذكي المؤسسية — HSA Group",
  description: "منصة الذكاء الاصطناعي المؤسسية الرسمية لمجموعة هائل سعيد أنعم — Hayel Saeed Anam Artificial Intelligence Platform",
  manifest: "/manifest.webmanifest",
  applicationName: "HSAAI",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "HSAAI",
  },
  icons: {
    icon: [
      { url: "/brand/hsa-logo.jpg" },
      { url: "/brand/hsaai-assistant-circle-256.png", sizes: "256x256", type: "image/png" },
      { url: "/brand/hsaai-assistant-circle-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/brand/hsaai-assistant-circle-256.png", sizes: "256x256", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // FIX v2.1 (P0): Removed maximumScale: 1 — it blocked user zoom and
  // violated WCAG 2.1 SC 1.4.4 (Resize Text). Users can now pinch-zoom on mobile.
  viewportFit: "cover",
  themeColor: "#FAFAFA",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <body>
        <Providers>
          {children}
          <FloatingAssistant />
          <RegisterServiceWorker />
        </Providers>
      </body>
    </html>
  );
}
