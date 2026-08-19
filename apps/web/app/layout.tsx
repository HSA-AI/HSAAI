import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans_Arabic, Inter, JetBrains_Mono } from "next/font/google";
import "../styles/globals.css";
import { Providers } from "@/providers/providers";
import { FloatingAssistant } from "@/components/assistant/floating-assistant";
import { RegisterServiceWorker } from "@/components/pwa/register-service-worker";

// ─── Font System (HSAAI Design System v2.0) ─────────────────────────────
// Primary: IBM Plex Sans Arabic (Arabic + Latin, enterprise-grade)
// Mono:    JetBrains Mono (code blocks, terminal output)
// Fallback: Inter (loaded as secondary for maximum Latin coverage)
const ibmPlexArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic", "latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-ibm-plex-arabic",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "HSAAI | HSA Internal AI Platform",
  description: "Official internal enterprise AI operating system for Hayel Saeed Anam Group",
  manifest: "/manifest.webmanifest",
  applicationName: "HSAAI",
  openGraph: {
    title: "HSAAI — Enterprise AI Platform",
    description: "منصة التشغيل الذكي المؤسسية — HSA Group",
    type: "website",
    locale: "ar_SA",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "HSAAI",
  },
  icons: {
    icon: [
      { url: "/brand/hsa-logo.png", type: "image/png" },
      { url: "/brand/hsaai-assistant-circle-256.png", sizes: "256x256", type: "image/png" },
      { url: "/brand/hsaai-assistant-circle-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/brand/hsaai-assistant-circle-256.png", sizes: "256x256", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // WCAG 2.1 SC 1.4.4: Allow user zoom (no maximumScale)
  viewportFit: "cover",
  themeColor: "#111111", // Official HSA brand black
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ar"
      dir="rtl"
      suppressHydrationWarning
      className={`${ibmPlexArabic.variable} ${inter.variable} ${jetbrainsMono.variable}`}
    >
      <body>
        <a href="#main-content" className="ds-skip-link">تخطي إلى المحتوى الرئيسي</a>
        <Providers>
          <div id="main-content">{children}</div>
          <FloatingAssistant />
          <RegisterServiceWorker />
        </Providers>
      </body>
    </html>
  );
}
