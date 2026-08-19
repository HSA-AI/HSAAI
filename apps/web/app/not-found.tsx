import Link from "next/link";

/**
 * FIX v2.1 (P0): Global not-found.tsx — shown when a route doesn't exist.
 * Previously there was no not-found.tsx, so 404s rendered Next.js default.
 */
export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="max-w-md w-full space-y-4 text-center">
        <div className="text-7xl font-black text-slate-200">404</div>
        <h2 className="text-xl font-bold text-slate-900">
          الصفحة غير موجودة
        </h2>
        <p className="text-sm text-slate-600">
          الصفحة التي تبحث عنها غير موجودة أو تم نقلها. يرجى التحقق من الرابط
          أو العودة إلى الصفحة الرئيسية.
        </p>
        <Link
          href="/"
          className="inline-block px-4 py-2 bg-slate-900 text-white rounded-md hover:bg-slate-800 transition-colors"
        >
          العودة إلى الرئيسية
        </Link>
      </div>
    </div>
  );
}
