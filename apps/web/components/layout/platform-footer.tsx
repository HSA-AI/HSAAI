import { brand } from "@/lib/brand";

/**
 * HSAAI Platform Footer — mirrors the official reference (index.html .footer):
 * dark surface #1A1A1A with gold title, white secondary lines.
 */
export function PlatformFooter() {
  return (
    <footer className="mt-auto border-t border-hsa-black-soft bg-hsa-black-soft px-4 py-6 text-center">
      <p className="text-sm font-bold text-hsa-yellow">
        <strong>{brand.platformName}</strong> — {brand.platformFullNameEn}
      </p>
      <p className="mt-1.5 text-xs text-white/70">{brand.footer.line2Ar}</p>
      <p className="mt-2 text-micro text-white/40">{brand.footer.copyright}</p>
    </footer>
  );
}
