"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import {
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  type ApiError,
} from "@/lib/safe-fetch";

type Analytics = {
  total_responses: number;
  active: number;
  total_hits: number;
  avg_relevance: number;
};

type MatchType = "exact" | "partial" | "keyword" | "regex";

type SmartResponse = {
  id: number;
  rule_name: string;
  intent: string;
  keywords: string[];
  match_type: MatchType;
  regex_pattern?: string;
  response_text: string;
  priority: number;
  enabled: boolean;
  language: string;
  workspace_id: string;
  usage_count: number;
};

type SmartResponseForm = Omit<
  SmartResponse,
  "id" | "usage_count"
>;

const emptyForm: SmartResponseForm = {
  rule_name: "",
  intent: "greeting",
  keywords: [],
  match_type: "keyword",
  regex_pattern: "",
  response_text: "",
  priority: 100,
  enabled: true,
  language: "ar",
  workspace_id: "default",
};

export default function SmartResponsesPage() {
  const [items, setItems] = useState<SmartResponse[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  const [form, setForm] =
    useState<SmartResponseForm>(emptyForm);

  const [editingId, setEditingId] =
    useState<number | null>(null);

  const [message, setMessage] = useState("");
  const [error, setError] =
    useState<ApiError | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [keywordText, setKeywordText] = useState("");

  const [pendingDelete, setPendingDelete] =
    useState<SmartResponse | null>(null);

  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);

    try {
      const [listRes, analyticsRes] = await Promise.all([
        apiGet<SmartResponse[]>(
          "/api/smart-responses",
        ),
        apiGet<Analytics>(
          "/api/smart-responses/analytics",
        ),
      ]);

      if (listRes.error) {
        setError(listRes.error);
        return;
      }

      if (analyticsRes.error) {
        setError(analyticsRes.error);
        return;
      }

      setItems(listRes.data ?? []);
      setAnalytics(analyticsRes.data ?? null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const sortedItems = useMemo(
    () =>
      [...items].sort(
        (a, b) => a.priority - b.priority,
      ),
    [items],
  );

  function resetForm() {
    setForm(emptyForm);
    setKeywordText("");
    setEditingId(null);
    setMessage("");
  }

  function editItem(item: SmartResponse) {
    setEditingId(item.id);

    setForm({
      rule_name: item.rule_name,
      intent: item.intent,
      keywords: item.keywords ?? [],
      match_type: item.match_type,
      regex_pattern: item.regex_pattern ?? "",
      response_text: item.response_text,
      priority: item.priority,
      enabled: item.enabled,
      language: item.language,
      workspace_id: item.workspace_id,
    });

    setKeywordText(
      (item.keywords ?? []).join(", "),
    );

    setMessage("");
    setError(null);

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  function updateKeywords(value: string) {
    setKeywordText(value);

    const keywords = value
      .split(",")
      .map((keyword) => keyword.trim())
      .filter(Boolean);

    setForm((current) => ({
      ...current,
      keywords,
    }));
  }

  function updateForm<K extends keyof SmartResponseForm>(
    key: K,
    value: SmartResponseForm[K],
  ) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function submit() {
    setMessage("");
    setError(null);
    setSaving(true);

    try {
      const payload: SmartResponseForm = {
        ...form,
        rule_name: form.rule_name.trim(),
        intent: form.intent.trim(),
        response_text: form.response_text.trim(),
        regex_pattern:
          form.regex_pattern?.trim() || "",
        workspace_id:
          form.workspace_id.trim() || "default",
        keywords: form.keywords
          .map((keyword) => keyword.trim())
          .filter(Boolean),
        priority: Number(form.priority),
      };

      const result = editingId
        ? await apiPut<SmartResponse>(
            `/api/smart-responses/${editingId}`,
            payload,
          )
        : await apiPost<SmartResponse>(
            "/api/smart-responses",
            payload,
          );

      if (result.error) {
        setError(result.error);
        return;
      }

      setMessage(
        editingId
          ? "تم تحديث الاستجابة الذكية بنجاح."
          : "تم إنشاء الاستجابة الذكية بنجاح.",
      );

      resetForm();
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }

    setDeleting(true);
    setError(null);
    setMessage("");

    try {
      const result = await apiDelete(
        `/api/smart-responses/${pendingDelete.id}`,
      );

      if (result.error) {
        setError(result.error);
        return;
      }

      setMessage(
        "تم حذف الاستجابة الذكية بنجاح.",
      );

      setPendingDelete(null);

      if (editingId === pendingDelete.id) {
        resetForm();
      }

      await load();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AppShell>
      <main className="space-y-6 p-4 md:p-6">
        <section className="rounded-3xl border border-slate-800 bg-slate-950 p-6 shadow-xl">
          <p className="text-sm font-bold text-hsa-yellow">
            HSAAI Enterprise
          </p>

          <h1 className="mt-2 text-3xl font-black text-white">
            الاستجابات الذكية
          </h1>

          <p className="mt-3 max-w-4xl leading-7 text-slate-400">
            إدارة قواعد الاستجابة التلقائية للمساعد
            الذكي داخل منصة HSAAI.
          </p>
        </section>

        {message && (
          <div
            className="rounded-xl border border-emerald-700/50 bg-emerald-950/40 p-4 text-sm text-emerald-300"
            role="status"
          >
            {message}
          </div>
        )}

        {error && (
          <div
            className="rounded-xl border border-red-700/50 bg-red-950/40 p-4 text-sm text-red-300"
            role="alert"
          >
            {error.message || "حدث خطأ أثناء تنفيذ العملية."}
          </div>
        )}

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="إجمالي القواعد"
            value={analytics?.total_responses ?? items.length}
          />

          <MetricCard
            label="القواعد النشطة"
            value={analytics?.active ?? 0}
          />

          <MetricCard
            label="إجمالي الاستخدام"
            value={analytics?.total_hits ?? 0}
          />

          <MetricCard
            label="متوسط الملاءمة"
            value={
              analytics
                ? `${Number(
                    analytics.avg_relevance,
                  ).toFixed(2)}`
                : "0.00"
            }
          />
        </section>

        <section className="rounded-3xl border border-slate-800 bg-slate-950 p-6">
          <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-black text-white">
                {editingId
                  ? "تعديل الاستجابة"
                  : "إنشاء استجابة جديدة"}
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                أضف قاعدة واضحة وقابلة للاختبار.
              </p>
            </div>

            {editingId && (
              <button
                type="button"
                onClick={resetForm}
                className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-bold text-slate-300 transition hover:bg-slate-900"
              >
                إلغاء التعديل
              </button>
            )}
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <Field
              label="اسم القاعدة"
              value={form.rule_name}
              onChange={(value) =>
                updateForm("rule_name", value)
              }
              placeholder="مثال: greeting-default"
            />

            <Field
              label="Intent"
              value={form.intent}
              onChange={(value) =>
                updateForm("intent", value)
              }
              placeholder="greeting"
            />

            <div>
              <label className="mb-2 block text-sm font-bold text-slate-300">
                نوع المطابقة
              </label>

              <select
                value={form.match_type}
                onChange={(event) =>
                  updateForm(
                    "match_type",
                    event.target.value as MatchType,
                  )
                }
                className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none focus:border-hsa-yellow"
              >
                <option value="exact">Exact</option>
                <option value="partial">Partial</option>
                <option value="keyword">Keyword</option>
                <option value="regex">Regex</option>
              </select>
            </div>

            <Field
              label="اللغة"
              value={form.language}
              onChange={(value) =>
                updateForm("language", value)
              }
              placeholder="ar"
            />

            <Field
              label="Workspace ID"
              value={form.workspace_id}
              onChange={(value) =>
                updateForm("workspace_id", value)
              }
              placeholder="default"
            />

            <div>
              <label className="mb-2 block text-sm font-bold text-slate-300">
                الأولوية
              </label>

              <input
                type="number"
                min={0}
                max={999999}
                value={form.priority}
                onChange={(event) =>
                  updateForm(
                    "priority",
                    Number(event.target.value),
                  )
                }
                className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none focus:border-hsa-yellow"
              />
            </div>

            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-bold text-slate-300">
                Keywords
              </label>

              <input
                type="text"
                value={keywordText}
                onChange={(event) =>
                  updateKeywords(event.target.value)
                }
                placeholder="مرحبا, أهلا, السلام عليكم"
                className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none focus:border-hsa-yellow"
              />

              <p className="mt-2 text-xs text-slate-500">
                افصل الكلمات باستخدام الفاصلة.
              </p>
            </div>

            {form.match_type === "regex" && (
              <div className="md:col-span-2">
                <label className="mb-2 block text-sm font-bold text-slate-300">
                  Regex Pattern
                </label>

                <input
                  type="text"
                  value={form.regex_pattern ?? ""}
                  onChange={(event) =>
                    updateForm(
                      "regex_pattern",
                      event.target.value,
                    )
                  }
                  placeholder="^(مرحبا|أهلا).*"
                  className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 font-mono text-white outline-none focus:border-hsa-yellow"
                />
              </div>
            )}

            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-bold text-slate-300">
                نص الاستجابة
              </label>

              <textarea
                value={form.response_text}
                onChange={(event) =>
                  updateForm(
                    "response_text",
                    event.target.value,
                  )
                }
                rows={6}
                placeholder="اكتب الاستجابة التي سيقدمها المساعد..."
                className="w-full resize-y rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 leading-7 text-white outline-none focus:border-hsa-yellow"
              />
            </div>

            <label className="flex items-center gap-3 text-sm font-bold text-slate-300">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(event) =>
                  updateForm(
                    "enabled",
                    event.target.checked,
                  )
                }
                className="h-5 w-5 rounded"
              />
              تفعيل القاعدة
            </label>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={saving}
              onClick={() => void submit()}
              className="rounded-xl bg-hsa-yellow px-6 py-3 font-black text-slate-950 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving
                ? "جارٍ الحفظ..."
                : editingId
                  ? "حفظ التعديلات"
                  : "إنشاء الاستجابة"}
            </button>

            <button
              type="button"
              onClick={resetForm}
              className="rounded-xl border border-slate-700 px-6 py-3 font-bold text-slate-300 transition hover:bg-slate-900"
            >
              إعادة ضبط
            </button>
          </div>
        </section>

        <section className="rounded-3xl border border-slate-800 bg-slate-950 p-6">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-black text-white">
                القواعد الحالية
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                {items.length} قاعدة مسجلة
              </p>
            </div>

            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-bold text-slate-300 hover:bg-slate-900 disabled:opacity-50"
            >
              تحديث
            </button>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-8 text-center text-slate-400">
              جارٍ تحميل الاستجابات...
            </div>
          ) : sortedItems.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/50 p-8 text-center text-slate-400">
              لا توجد استجابات ذكية مسجلة حاليًا.
            </div>
          ) : (
            <div className="space-y-4">
              {sortedItems.map((item) => (
                <article
                  key={item.id}
                  className="rounded-2xl border border-slate-800 bg-slate-900 p-5"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-black text-white">
                          {item.rule_name}
                        </h3>

                        <Badge
                          active={item.enabled}
                        />

                        <span className="rounded-lg bg-slate-800 px-2 py-1 text-xs font-bold text-slate-300">
                          {item.match_type}
                        </span>

                        <span className="rounded-lg bg-slate-800 px-2 py-1 text-xs font-bold text-slate-300">
                          P{item.priority}
                        </span>
                      </div>

                      <p className="mt-2 text-sm text-slate-400">
                        Intent: {item.intent}
                      </p>

                      <p className="mt-3 whitespace-pre-wrap leading-7 text-slate-200">
                        {item.response_text}
                      </p>

                      {item.keywords?.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {item.keywords.map(
                            (keyword) => (
                              <span
                                key={`${item.id}-${keyword}`}
                                className="rounded-lg bg-slate-800 px-2 py-1 text-xs text-slate-400"
                              >
                                {keyword}
                              </span>
                            ),
                          )}
                        </div>
                      )}

                      <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
                        <span>
                          الاستخدام:{" "}
                          {item.usage_count ?? 0}
                        </span>

                        <span>
                          اللغة: {item.language}
                        </span>

                        <span>
                          Workspace:{" "}
                          {item.workspace_id}
                        </span>
                      </div>
                    </div>

                    <div className="flex shrink-0 gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          editItem(item)
                        }
                        className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-bold text-slate-300 hover:bg-slate-800"
                      >
                        تعديل
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          setPendingDelete(item)
                        }
                        className="rounded-xl border border-red-900/70 px-4 py-2 text-sm font-bold text-red-400 hover:bg-red-950/40"
                      >
                        حذف
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        {pendingDelete && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
          >
            <div className="w-full max-w-md rounded-3xl border border-slate-700 bg-slate-950 p-6 shadow-2xl">
              <h2
                id="delete-title"
                className="text-xl font-black text-white"
              >
                تأكيد الحذف
              </h2>

              <p className="mt-3 leading-7 text-slate-400">
                هل تريد حذف القاعدة:
                <strong className="mx-1 text-white">
                  {pendingDelete.rule_name}
                </strong>
                ؟
              </p>

              <p className="mt-2 text-sm text-red-400">
                هذا الإجراء لا يمكن التراجع عنه.
              </p>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  disabled={deleting}
                  onClick={() =>
                    setPendingDelete(null)
                  }
                  className="rounded-xl border border-slate-700 px-5 py-3 font-bold text-slate-300 hover:bg-slate-900 disabled:opacity-50"
                >
                  إلغاء
                </button>

                <button
                  type="button"
                  disabled={deleting}
                  onClick={() =>
                    void confirmDelete()
                  }
                  className="rounded-xl bg-red-700 px-5 py-3 font-black text-white hover:bg-red-600 disabled:opacity-50"
                >
                  {deleting
                    ? "جارٍ الحذف..."
                    : "تأكيد الحذف"}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </AppShell>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-bold text-slate-300">
        {label}
      </label>

      <input
        type="text"
        value={value}
        onChange={(event) =>
          onChange(event.target.value)
        }
        placeholder={placeholder}
        className="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none focus:border-hsa-yellow"
      />
    </div>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950 p-5">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
        {label}
      </p>

      <strong className="mt-2 block text-3xl font-black text-white">
        {value}
      </strong>
    </div>
  );
}

function Badge({
  active,
}: {
  active: boolean;
}) {
  return (
    <span
      className={`rounded-lg px-2 py-1 text-xs font-bold ${
        active
          ? "bg-emerald-950 text-emerald-400"
          : "bg-slate-800 text-slate-500"
      }`}
    >
      {active ? "نشط" : "متوقف"}
    </span>
  );
}
