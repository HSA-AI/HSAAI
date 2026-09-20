import Link from "next/link";

/**
 * FIX v2.1 (P0): Global not-found.tsx — shown when a route doesn't exist.
 * Restyled with the HSAAI design system (light enterprise, gold accent).
 */
export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center bg-hsa-bg p-6">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-hsa-border bg-white p-8 text-center shadow-hsa-card">
        <div className="text-6xl font-bold text-hsa-soft" aria-hidden>404</div>
        <h2 className="text-xl font-bold text-hsa-black">الصفحة غير موجودة</h2>
        <p className="text-sm leading-7 text-hsa-secondary">
          الصفحة التي تبحث عنها غير موجودة أو تم نقلها. يرجى التحقق من الرابط
          أو العودة إلى الصفحة الرئيسية.
        </p>
        <Link
          href="/"
          className="inline-flex min-h-11 items-center justify-center rounded-xl bg-hsa-yellow px-4 py-2.5 text-sm font-bold text-hsa-black transition hover:bg-hsa-gold-dark hover:text-white"
        >
          العودة إلى الرئيسية
        </Link>
      </div>
    </div>
  );
}
