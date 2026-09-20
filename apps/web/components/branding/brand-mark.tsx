import Image from "next/image";
import { brand } from "@/lib/brand";

/**
 * HSAAI Brand Mark — official logo with protected aspect ratio & clear space.
 * Subtitle follows the official identity: منصة التشغيل الذكي المؤسسية
 */
export function BrandMark({ compact = false, size = 48 }: { compact?: boolean; size?: number }) {
  return (
    <div className="flex items-center gap-3">
      <span
        className="relative shrink-0 overflow-hidden rounded-xl border-2 border-hsa-yellow bg-white"
        style={{ width: size, height: size }}
      >
        <Image src={brand.logoPath} alt="HSAAI Official Logo" fill sizes={`${size}px`} className="object-contain p-0.5" priority />
      </span>
      {!compact && (
        <div className="min-w-0 leading-tight">
          <p className="text-base font-bold text-hsa-black">{brand.platformName}</p>
          <p className="truncate text-micro font-semibold text-hsa-secondary">{brand.platformFullNameAr}</p>
        </div>
      )}
    </div>
  );
}
