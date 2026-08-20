"use client";

import { useMemo, useState } from "react";
import {
  BookOpenText,
  FileText,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

type KnowledgeStatus = "متاح" | "مقيد";

type KnowledgeItem = {
  id: string;
  title: string;
  description: string;
  category: string;
  type: string;
  status: KnowledgeStatus;
};

const KNOWLEDGE_ITEMS: readonly KnowledgeItem[] = [
  {
    id: "policies",
    title: "السياسات والإجراءات",
    description:
      "مستودع مركزي للسياسات والإجراءات واللوائح المؤسسية المصرح بالوصول إليها.",
    category: "السياسات",
    type: "وثائق",
    status: "متاح",
  },
  {
    id: "reports",
    title: "التقارير المؤسسية",
    description:
      "الوصول إلى التقارير والمعلومات المؤسسية وفق الصلاحيات المعتمدة.",
    category: "التقارير",
    type: "تقارير",
    status: "متاح",
  },
  {
    id: "hr",
    title: "الموارد البشرية",
    description:
      "المعرفة والوثائق المتعلقة بالموارد البشرية والخدمات الداخلية.",
    category: "الموارد البشرية",
    type: "وثائق",
    status: "مقيد",
  },
  {
    id: "finance",
    title: "المالية",
    description:
      "المعلومات المالية والوثائق التشغيلية المتاحة حسب مستوى الصلاحية.",
    category: "المالية",
    type: "وثائق",
    status: "مقيد",
  },
  {
    id: "technology",
    title: "التقنية والأنظمة",
    description:
      "معرفة تقنية حول الأنظمة والبنية التحتية والخدمات الرقمية المؤسسية.",
    category: "التقنية",
    type: "معرفة تقنية",
    status: "متاح",
  },
  {
    id: "governance",
    title: "الحوكمة والأمن",
    description:
      "المحتوى المتعلق بالحوكمة والأمن والامتثال وإدارة الوصول.",
    category: "الحوكمة",
    type: "معرفة مؤسسية",
    status: "مقيد",
  },
];

const CATEGORIES = [
  "الكل",
  ...Array.from(new Set(KNOWLEDGE_ITEMS.map((item) => item.category))),
];

const TOTAL_SOURCES = KNOWLEDGE_ITEMS.length;

const AVAILABLE_SOURCES = KNOWLEDGE_ITEMS.filter(
  (item) => item.status === "متاح",
).length;

const RESTRICTED_SOURCES = KNOWLEDGE_ITEMS.filter(
  (item) => item.status === "مقيد",
).length;

export default function KnowledgeHubPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("الكل");

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();

    return KNOWLEDGE_ITEMS.filter((item) => {
      if (category !== "الكل" && item.category !== category) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      const searchableText = [
        item.title,
        item.description,
        item.category,
        item.type,
        item.status,
      ]
        .join(" ")
        .toLocaleLowerCase();

      return searchableText.includes(normalizedQuery);
    });
  }, [category, query]);

  return (
    <main
      dir="rtl"
      className="min-h-dvh bg-slate-50 px-4 py-6 text-slate-900 dark:bg-hsa-black dark:text-white sm:px-6 lg:px-8"
    >
      <div className="mx-auto max-w-7xl">
        <header className="mb-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="mb-3 flex items-center gap-2 text-hsa-yellow">
                <BookOpenText size={22} aria-hidden="true" />
                <span className="text-sm font-black">
                  HSAAI Knowledge Hub
                </span>
              </div>

              <h1 className="text-3xl font-black tracking-tight sm:text-4xl">
                مركز المعرفة المؤسسية
              </h1>

              <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600 dark:text-slate-400">
                منصة مركزية لاستكشاف المعرفة والوثائق المؤسسية المتاحة وفق
                الصلاحيات والسياسات المعتمدة.
              </p>
            </div>

            <div className="flex items-center gap-2 rounded-2xl border border-hsa-yellow/20 bg-white px-4 py-3 text-sm font-bold shadow-sm dark:bg-white/[0.04]">
              <ShieldCheck
                size={18}
                className="text-hsa-yellow"
                aria-hidden="true"
              />
              <span>الوصول محكوم بالصلاحيات</span>
            </div>
          </div>
        </header>

        <section
          aria-label="البحث والتصفية"
          className="mb-6 rounded-3xl border border-hsa-yellow/20 bg-white p-4 shadow-sm dark:bg-white/[0.03]"
        >
          <div className="flex flex-col gap-4 lg:flex-row">
            <label className="relative flex-1">
              <span className="sr-only">البحث في مركز المعرفة</span>

              <Search
                size={19}
                aria-hidden="true"
                className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-400"
              />

              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="ابحث في المعرفة المؤسسية..."
                aria-label="البحث في المعرفة المؤسسية"
                className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-11 text-sm outline-none transition focus:border-hsa-yellow focus:ring-2 focus:ring-hsa-yellow/20 dark:border-white/10 dark:bg-black/20"
              />
            </label>

            <div
              className="flex flex-wrap gap-2"
              role="group"
              aria-label="تصنيف المعرفة"
            >
              {CATEGORIES.map((item) => {
                const active = category === item;

                return (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setCategory(item)}
                    aria-pressed={active}
                    className={`rounded-2xl px-4 py-2.5 text-sm font-bold transition ${
                      active
                        ? "bg-hsa-yellow text-black shadow-sm"
                        : "border border-slate-200 bg-white text-slate-700 hover:bg-hsa-yellow/10 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-300"
                    }`}
                  >
                    {item}
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        <section
          aria-label="إحصائيات مركز المعرفة"
          className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <div className="rounded-3xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-white/[0.03]">
            <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-hsa-yellow/15 text-hsa-yellow">
              <FileText size={21} aria-hidden="true" />
            </div>

            <p className="text-2xl font-black">{TOTAL_SOURCES}</p>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              مصادر معرفة
            </p>
          </div>

          <div className="rounded-3xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-white/[0.03]">
            <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-hsa-yellow/15 text-hsa-yellow">
              <Sparkles size={21} aria-hidden="true" />
            </div>

            <p className="text-2xl font-black">{AVAILABLE_SOURCES}</p>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              مصادر متاحة
            </p>
          </div>

          <div className="rounded-3xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-white/[0.03]">
            <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-hsa-yellow/15 text-hsa-yellow">
              <ShieldCheck size={21} aria-hidden="true" />
            </div>

            <p className="text-2xl font-black">{RESTRICTED_SOURCES}</p>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              مصادر محكومة بالصلاحيات
            </p>
          </div>
        </section>

        <section aria-labelledby="knowledge-sources-heading">
          <div className="mb-4">
            <h2 id="knowledge-sources-heading" className="text-xl font-black">
              مصادر المعرفة
            </h2>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {filteredItems.length} نتيجة مطابقة
            </p>
          </div>

          {filteredItems.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-white/10 dark:bg-white/[0.03]">
              <Search
                size={32}
                aria-hidden="true"
                className="mx-auto mb-3 text-slate-400"
              />

              <h3 className="font-black">لم يتم العثور على نتائج</h3>

              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                جرّب تغيير عبارة البحث أو اختيار تصنيف آخر.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {filteredItems.map((item) => (
                <article
                  key={item.id}
                  className="group rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-hsa-yellow/40 hover:shadow-md dark:border-white/10 dark:bg-white/[0.03]"
                >
                  <div className="mb-5 flex items-start justify-between gap-3">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-hsa-yellow/10 text-hsa-yellow">
                      <FileText size={22} aria-hidden="true" />
                    </div>

                    <span
                      className={`rounded-full px-3 py-1 text-[11px] font-black ${
                        item.status === "متاح"
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>

                  <h3 className="text-lg font-black">{item.title}</h3>

                  <p className="mt-3 min-h-20 text-sm leading-7 text-slate-600 dark:text-slate-400">
                    {item.description}
                  </p>

                  <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 text-xs dark:border-white/10">
                    <span className="font-bold text-hsa-yellow">
                      {item.category}
                    </span>

                    <span className="text-slate-400">{item.type}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
