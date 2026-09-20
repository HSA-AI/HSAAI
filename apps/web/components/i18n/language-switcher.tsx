"use client";

import { useState } from "react";
import { Globe } from "lucide-react";
import { changeLanguage, getCurrentLanguage, type SupportedLanguage } from "@/lib/i18n";

/**
 * HSAAI Language Switcher — AR (RTL) ⇄ EN (LTR)
 * Persists via i18next localStorage detector key `hsaai-language`.
 */
export function LanguageSwitcher() {
  const [lang, setLang] = useState<SupportedLanguage>(getCurrentLanguage());

  async function toggle() {
    const next: SupportedLanguage = lang === "ar" ? "en" : "ar";
    setLang(next);
    await changeLanguage(next);
  }

  return (
    <button
      type="button"
      onClick={() => void toggle()}
      className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-hsa-border bg-white px-3 text-xs font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft"
      aria-label={lang === "ar" ? "Switch to English" : "التبديل إلى العربية"}
      title={lang === "ar" ? "English" : "العربية"}
    >
      <Globe size={15} className="text-hsa-gold" />
      {lang === "ar" ? "EN" : "عربي"}
    </button>
  );
}
