/**
 * FIX v2.1 (P0): Global loading.tsx — shown during route transitions.
 * Previously there was no loading.tsx, so every route transition showed
 * a blank screen until the page finished rendering.
 */
export default function Loading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="min-h-[60vh] flex items-center justify-center"
    >
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 rounded-full border-4 border-slate-200 border-t-slate-900 animate-spin" />
        <p className="text-sm text-slate-500">جارٍ التحميل...</p>
      </div>
    </div>
  );
}
