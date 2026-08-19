import Image from "next/image";
import { brand } from "@/lib/brand";

export function BrandMark({ compact = false, size }: { compact?: boolean; size?: number }) {
  const dimension = size ?? 48;
  return (
    <div className="flex items-center gap-3">
      <div
        className="relative overflow-hidden rounded-2xl border border-hsa-yellow/40 bg-white shadow-sm"
        style={{ width: dimension, height: dimension }}
      >
        <Image
          src={brand.logoPath}
          alt="HSA Logo"
          fill
          sizes={`${dimension}px`}
          className="object-contain p-1"
          priority
        />
      </div>
      {!compact && (
        <div className="leading-tight">
          <p className="text-sm font-bold text-hsa-black dark:text-white">{brand.companyNameAr}</p>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{brand.platformName}</p>
        </div>
      )}
    </div>
  );
}
