/**
 * FIX v2.1 (P0): Global loading.tsx — shown during route transitions.
 * Restyled with the HSAAI design system: gold spinner on light background.
 */
export default function Loading() {
  return (
    <div role="status" aria-live="polite" className="flex min-h-[60vh] items-center justify-center bg-hsa-bg">
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-hsa-soft border-t-hsa-yellow" />
        <p className="text-sm font-bold text-hsa-secondary">جارٍ التحميل...</p>
      </div>
    </div>
  );
}
