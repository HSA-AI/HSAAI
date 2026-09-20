"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/ui/kpi-card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { LoadingState } from "@/components/enterprise/page-state";
import { CornerDownRight, LayoutTemplate, Target, Zap } from "lucide-react";

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

function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="text-xs font-bold text-hsa-secondary">{children}</span>;
}

export default function SmartResponsesPage() {
  const [items, setItems] = useState<SmartResponse[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  // FIX-MEDIUM-LOW-FINAL: Replaced blocking window.confirm() with a state-driven
  // confirmation modal. The previous call froze the main thread and was not
  // dismissible across tabs; the API still validates the DELETE so this is purely UX.
  const [pendingDelete, setPendingDelete] = useState<SmartResponse | null>(null);

  async function load() {
    setLoading(true);
    const [listRes, analyticsRes] = await Promise.all([fetch("/api/smart-responses"), fetch("/api/smart-responses/analytics")]);
    setItems(await listRes.json());
    setAnalytics(await analyticsRes.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  const keywordText = useMemo(() => form.keywords.join("، "), [form.keywords]);

  async function submit() {
    setMessage("");
    const payload = { ...form };
    const res = await fetch(editingId ? `/api/smart-responses/${editingId}` : "/api/smart-responses", {
      method: editingId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      setMessage(await res.text());
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
      <main className="space-y-6">
        <PageHeader
          eyebrow="HSAAI Smart Responses Engine"
          title="محرك الردود الذكية الجاهزة"
          description="طبقة مؤسسية قبل نموذج الذكاء الاصطناعي لاكتشاف نية المستخدم وإرجاع ردود جاهزة عند تطابق Exact أو Partial أو Keyword أو Regex."
        />

        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard label="Smart Hits" value={analytics?.smart_response_hits ?? 0} icon={<Zap size={20} />} />
          <KpiCard label="LLM Fallbacks" value={analytics?.llm_fallbacks ?? 0} icon={<CornerDownRight size={20} />} />
          <KpiCard label="Match Rate" value={`${Math.round((analytics?.match_rate ?? 0) * 100)}%`} icon={<Target size={20} />} />
          <KpiCard label="Templates" value={items.length} icon={<LayoutTemplate size={20} />} />
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.4fr]">
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">{editingId ? "تعديل رد" : "إضافة رد جديد"}</h2>
            <div className="mt-5 space-y-4">
              <label className="block">
                <FieldLabel>اسم القاعدة</FieldLabel>
                <Input className="mt-1.5" value={form.rule_name} onChange={(e) => setForm({ ...form, rule_name: e.target.value })} />
              </label>
              <label className="block">
                <FieldLabel>Intent</FieldLabel>
                <Input className="mt-1.5" value={form.intent} onChange={(e) => setForm({ ...form, intent: e.target.value })} />
              </label>
              <label className="block">
                <FieldLabel>الكلمات المفتاحية، افصل بينها بفاصلة</FieldLabel>
                <Input className="mt-1.5" value={keywordText} onChange={(e) => setForm({ ...form, keywords: e.target.value.split(/[،,|]/).map((x) => x.trim()).filter(Boolean) })} />
              </label>
              <label className="block">
                <FieldLabel>Match Type</FieldLabel>
                <select className="hsa-input mt-1.5" value={form.match_type} onChange={(e) => setForm({ ...form, match_type: e.target.value as any })} aria-label="نوع المطابقة">
                  <option value="keyword">Keyword</option>
                  <option value="exact">Exact</option>
                  <option value="partial">Partial</option>
                  <option value="regex">Regex</option>
                </select>
              </label>
              <label className="block">
                <FieldLabel>Regex Pattern</FieldLabel>
                <Input className="mt-1.5" value={form.regex_pattern || ""} onChange={(e) => setForm({ ...form, regex_pattern: e.target.value })} />
              </label>
              <label className="block">
                <FieldLabel>الرد الجاهز</FieldLabel>
                <Textarea className="mt-1.5 min-h-32" value={form.response_text} onChange={(e) => setForm({ ...form, response_text: e.target.value })} />
              </label>
              <label className="block">
                <FieldLabel>Priority</FieldLabel>
                <Input className="mt-1.5" type="number" value={String(form.priority)} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} />
              </label>
              <label className="flex items-center gap-3 text-sm text-hsa-black">
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} className="h-4 w-4 accent-hsa-gold" /> مفعّل
              </label>
              <div className="flex gap-3">
                <Button onClick={submit}>حفظ</Button>
                {editingId && <Button variant="secondary" onClick={() => { setEditingId(null); setForm(emptyForm); }}>إلغاء</Button>}
              </div>
              {message && <p role="status" className="text-sm font-bold text-hsa-gold">{message}</p>}
            </div>
          </Card>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-bold text-hsa-black">Response Templates</h2>
              <div className="flex gap-2 text-xs">
                <a download href="/api/smart-responses/export/json" className="inline-flex items-center rounded-xl border border-hsa-border bg-white px-3 py-2 font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft">JSON</a>
                <a download href="/api/smart-responses/export/csv" className="inline-flex items-center rounded-xl border border-hsa-border bg-white px-3 py-2 font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft">CSV</a>
                <a download href="/api/smart-responses/export/excel" className="inline-flex items-center rounded-xl border border-hsa-border bg-white px-3 py-2 font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft">Excel</a>
              </div>
            </div>
            <div className="mt-5 overflow-x-auto">
              <table className="hsa-table min-w-[900px]">
                <thead>
                  <tr><th>Rule</th><th>Intent</th><th>Match</th><th>Priority</th><th>Usage</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>
                  {loading ? <tr><td className="p-3" colSpan={7}><LoadingState label="جارٍ تحميل الردود الجاهزة..." /></td></tr> : items.map((item) => (
                    <tr key={item.id}>
                      <td><p className="font-bold text-hsa-black">{item.rule_name}</p><p className="mt-1 max-w-md truncate text-xs text-hsa-secondary">{item.response_text}</p></td>
                      <td>{item.intent}</td>
                      <td>{item.match_type}</td>
                      <td>{item.priority}</td>
                      <td>{item.usage_count}</td>
                      <td><Badge tone={item.enabled ? "ok" : "neutral"}>{item.enabled ? "Enabled" : "Disabled"}</Badge></td>
                      <td>
                        <div className="flex flex-wrap gap-2 whitespace-nowrap">
                          <Button variant="secondary" className="px-3 py-1 text-xs" onClick={() => edit(item)}>Edit</Button>
                          <Button variant="secondary" className="px-3 py-1 text-xs" onClick={() => toggle(item.id)}>Toggle</Button>
                          <Button variant="secondary" className="px-3 py-1 text-xs text-red-700 hover:border-red-300 hover:bg-red-50 hover:text-red-700" onClick={() => setPendingDelete(item)}>Delete</Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>

        {pendingDelete && (
          <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-sm rounded-3xl border border-hsa-border bg-white p-6 text-center shadow-hsa-card">
              <h3 className="text-lg font-bold text-hsa-black">تأكيد الحذف</h3>
              <p className="mt-2 text-sm leading-7 text-hsa-secondary">
                هل تريد حذف الرد «{pendingDelete.rule_name}»؟ لا يمكن التراجع عن هذا الإجراء.
              </p>
              <div className="mt-5 flex justify-center gap-3">
                <Button variant="secondary" onClick={() => setPendingDelete(null)}>إلغاء</Button>
                <Button onClick={confirmDelete} className="bg-red-600 text-white hover:bg-red-700 hover:text-white">حذف</Button>
              </div>
            </div>
          </div>
        )}
      </main>
    </AppShell>
  );
}
