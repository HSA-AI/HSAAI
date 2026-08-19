"use client";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/safe-fetch";
import type { ApiError } from "@/lib/safe-fetch";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";

type Analytics = { total_responses: number; active: number; total_hits: number; avg_relevance: number };
type SmartResponse = {
  id: number;
  rule_name: string;
  intent: string;
  keywords: string[];
  match_type: "exact" | "partial" | "keyword" | "regex";
  regex_pattern?: string;
  response_text: string;
  priority: number;
  enabled: boolean;
  language: string;
  workspace_id: string;
  usage_count: number;
};

const emptyForm: Omit<SmartResponse, "id" | "usage_count"> = {
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
  const [analytics, setAnalytics] = useState<any>(null);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  // FIX-MEDIUM-LOW-FINAL: Replaced blocking window.confirm() with a state-driven
  // confirmation modal. The previous call froze the main thread and was not
  // dismissible across tabs; the API still validates the DELETE so this is purely UX.
  const [pendingDelete, setPendingDelete] = useState<SmartResponse | null>(null);

  // FIX V3: Use enterprise safeFetch — never use raw fetch with .json() without ok check
  async function load() {
    setLoading(true);
    const [listRes, analyticsRes] = await Promise.all([
      apiGet<SmartResponse[]>("/api/smart-responses"),
      apiGet<Analytics>("/api/smart-responses/analytics"),
    ]);
    if (listRes.error || analyticsRes.error) {
      setError(listRes.error || analyticsRes.error);
    } else {
      setItems(listRes.data || []);
      setAnalytics(analyticsRes.data);
    }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  const keywordText = useMemo(() => form.keywords.join("، "), [form.keywords]);

  async function submit() {
    setMessage("");
    const payload = { ...form };
    const result = editingId
      ? await apiPut(`/api/smart-responses/${editingId}`, payload)
      : await apiPost("/api/smart-responses", payload);
    if (result.error) {
      setMessage(result.error.message);
      return;
    }
    setForm(emptyForm);
    setEditingId(null);
    setMessage("تم حفظ الرد الجاهز بنجاح.");
    await load();
  }

  async function remove(id: number) {
    await fetch(`/api/smart-responses/${id}`, { method: "DELETE" });
    await load();
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const id = pendingDelete.id;
    setPendingDelete(null);
    await remove(id);
  }

  async function toggle(id: number) {
    await fetch(`/api/smart-responses/${id}/toggle`, { method: "PATCH" });
    await load();
  }

  function edit(item: SmartResponse) {
    setEditingId(item.id);
    setForm({
      rule_name: item.rule_name,
      intent: item.intent,
      keywords: item.keywords || [],
      match_type: item.match_type,
      regex_pattern: item.regex_pattern || "",
      response_text: item.response_text,
      priority: item.priority,
      enabled: item.enabled,
      language: item.language || "ar",
      workspace_id: item.workspace_id || "default",
    });
  }

  return (
    <AppShell>
      <main className="space-y-6 overflow-x-hidden">
        <section className="rounded-[2rem] border border-hsa-yellow/20 bg-gradient-to-br from-black via-slate-950 to-black p-6 text-white shadow-hsa-glow sm:p-8">
          <p className="text-xs font-black uppercase tracking-[0.35em] text-hsa-yellow">HSAAI Smart Responses Engine</p>
          <h1 className="mt-4 text-3xl font-black md:text-5xl">محرك الردود الذكية الجاهزة</h1>
          <p className="mt-4 max-w-4xl text-sm leading-8 text-slate-300 md:text-base">
            طبقة مؤسسية قبل نموذج الذكاء الاصطناعي لاكتشاف نية المستخدم وإرجاع ردود جاهزة عند تطابق Exact أو Partial أو Keyword أو Regex.
          </p>
        </section>

        <section className="grid gap-4 md:grid-cols-4">
          <Metric title="Smart Hits" value={analytics?.smart_response_hits ?? 0} />
          <Metric title="LLM Fallbacks" value={analytics?.llm_fallbacks ?? 0} />
          <Metric title="Match Rate" value={`${Math.round((analytics?.match_rate ?? 0) * 100)}%`} />
          <Metric title="Templates" value={items.length} />
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.4fr]">
          <div className="rounded-3xl border border-slate-800 bg-slate-950 p-5 text-white">
            <h2 className="text-xl font-black">{editingId ? "تعديل رد" : "إضافة رد جديد"}</h2>
            <div className="mt-5 space-y-4">
              <Input label="اسم القاعدة" value={form.rule_name} onChange={(v) => setForm({ ...form, rule_name: v })} />
              <Input label="Intent" value={form.intent} onChange={(v) => setForm({ ...form, intent: v })} />
              <Input label="الكلمات المفتاحية، افصل بينها بفاصلة" value={keywordText} onChange={(v) => setForm({ ...form, keywords: v.split(/[،,|]/).map((x) => x.trim()).filter(Boolean) })} />
              <label className="block text-sm text-slate-300">Match Type</label>
              <select className="w-full rounded-2xl border border-slate-700 bg-black p-3 text-white" value={form.match_type} onChange={(e) => setForm({ ...form, match_type: e.target.value as any })}>
                <option value="keyword">Keyword</option>
                <option value="exact">Exact</option>
                <option value="partial">Partial</option>
                <option value="regex">Regex</option>
              </select>
              <Input label="Regex Pattern" value={form.regex_pattern || ""} onChange={(v) => setForm({ ...form, regex_pattern: v })} />
              <label className="block text-sm text-slate-300">الرد الجاهز</label>
              <textarea className="min-h-32 w-full rounded-2xl border border-slate-700 bg-black p-3 text-white" value={form.response_text} onChange={(e) => setForm({ ...form, response_text: e.target.value })} />
              <Input label="Priority" type="number" value={String(form.priority)} onChange={(v) => setForm({ ...form, priority: Number(v) })} />
              <div className="flex items-center gap-3 text-sm text-slate-300"><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> مفعّل</div>
              <div className="flex gap-3">
                <button onClick={submit} className="rounded-2xl bg-hsa-yellow px-5 py-3 font-black text-black">حفظ</button>
                {editingId && <button onClick={() => { setEditingId(null); setForm(emptyForm); }} className="rounded-2xl border border-slate-700 px-5 py-3 text-white">إلغاء</button>}
              </div>
              {message && <p className="text-sm text-hsa-yellow">{message}</p>}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-white p-5 text-slate-950 shadow-xl dark:bg-slate-950 dark:text-white">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-black">Response Templates</h2>
              <div className="flex gap-2 text-xs">
                <a href="/api/smart-responses/export/json" className="rounded-xl border px-3 py-2">JSON</a>
                <a href="/api/smart-responses/export/csv" className="rounded-xl border px-3 py-2">CSV</a>
                <a href="/api/smart-responses/export/excel" className="rounded-xl border px-3 py-2">Excel</a>
              </div>
            </div>
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[900px] text-sm">
                <thead className="text-left text-slate-500"><tr><th className="p-3">Rule</th><th>Intent</th><th>Match</th><th>Priority</th><th>Usage</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>
                  {loading ? <tr><td className="p-3" colSpan={7}>Loading...</td></tr> : items.map((item) => (
                    <tr key={item.id} className="border-t border-slate-200 dark:border-slate-800">
                      <td className="p-3"><p className="font-bold">{item.rule_name}</p><p className="mt-1 max-w-md truncate text-xs text-slate-500">{item.response_text}</p></td>
                      <td>{item.intent}</td>
                      <td>{item.match_type}</td>
                      <td>{item.priority}</td>
                      <td>{item.usage_count}</td>
                      <td>{item.enabled ? "Enabled" : "Disabled"}</td>
                      <td className="space-x-2 whitespace-nowrap">
                        <button onClick={() => edit(item)} className="rounded-lg border px-3 py-1">Edit</button>
                        <button onClick={() => toggle(item.id)} className="rounded-lg border px-3 py-1">Toggle</button>
                        <button onClick={() => setPendingDelete(item)} className="rounded-lg border px-3 py-1 text-red-500">Delete</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {pendingDelete && (
          <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-sm rounded-3xl border border-slate-200 bg-white p-6 text-center shadow-xl dark:border-slate-800 dark:bg-slate-950">
              <h3 className="text-lg font-black text-slate-900 dark:text-white">تأكيد الحذف</h3>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                هل تريد حذف الرد «{pendingDelete.rule_name}»؟ لا يمكن التراجع عن هذا الإجراء.
              </p>
              <div className="mt-5 flex justify-center gap-3">
                <button
                  onClick={() => setPendingDelete(null)}
                  className="rounded-2xl border border-slate-300 px-5 py-2 text-sm font-bold text-slate-700 dark:border-slate-700 dark:text-slate-200"
                >
                  إلغاء
                </button>
                <button
                  onClick={confirmDelete}
                  className="rounded-2xl bg-red-600 px-5 py-2 text-sm font-bold text-white hover:bg-red-700"
                >
                  حذف
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </AppShell>
  );
}

function Metric({ title, value }: { title: string; value: string | number }) {
  return <div className="rounded-3xl border border-slate-800 bg-slate-950 p-5 text-white"><p className="text-xs uppercase tracking-[0.25em] text-hsa-yellow">{title}</p><p className="mt-3 text-3xl font-black">{value}</p></div>;
}

function Input({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return <label className="block"><span className="text-sm text-slate-300">{label}</span><input type={type} className="mt-2 w-full rounded-2xl border border-slate-700 bg-black p-3 text-white" value={value} onChange={(e) => onChange(e.target.value)} /></label>;
}
