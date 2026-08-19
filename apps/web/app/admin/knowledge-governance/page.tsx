"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
// FIX F-02: api is a default export — was using named import causing TS2305 build error.
import api from "@/services/api";
import { can, getClientRoles } from "@/lib/security/rbac";

type KnowledgeDocument = {
  document_id: string;
  filename: string;
  title?: string;
  status: "draft" | "pending_review" | "approved" | "rejected" | "archived" | string;
  classification?: string;
  sensitivity?: string;
  department?: string;
  uploaded_by?: string;
  created_at?: string;
};

type Analytics = { documents?: number; sensitive_documents?: number; by_status?: Record<string, number> };

const statusClass: Record<string, string> = {
  approved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  pending_review: "bg-amber-50 text-amber-700 ring-amber-200",
  rejected: "bg-rose-50 text-rose-700 ring-rose-200",
  archived: "bg-slate-100 text-slate-600 ring-slate-200",
  draft: "bg-blue-50 text-blue-700 ring-blue-200",
};

function StatusBadge({ status }: { status: string }) {
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${statusClass[status] || statusClass.draft}`}>{status}</span>;
}

export default function KnowledgeGovernancePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [analytics, setAnalytics] = useState<Analytics>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const roles = typeof window !== "undefined" ? getClientRoles() : [];
  const canReview = can("knowledge:review", roles);
  const canDelete = can("knowledge:delete", roles);

  async function load() {
    setLoading(true); setError("");
    try {
      const [docs, stats] = await Promise.all([
        api.get("/v1/knowledge-hub/documents"),
        api.get("/v1/knowledge-hub/analytics"),
      ]);
      setDocuments(docs.data || []);
      setAnalytics(stats.data || {});
    } catch {
      setError("تعذر تحميل بيانات الحوكمة. تحقق من الاتصال والصلاحيات.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const rows = useMemo(() => filter === "all" ? documents : documents.filter((d) => d.status === filter), [documents, filter]);
  const statusCounts = analytics.by_status || {};
  const cards = [
    ["إجمالي الوثائق", analytics.documents || documents.length],
    ["بانتظار المراجعة", statusCounts.pending_review || 0],
    ["حساسة", analytics.sensitive_documents || 0],
    ["مرفوضة", statusCounts.rejected || 0],
    ["مؤرشفة", statusCounts.archived || 0],
  ];

  async function action(documentId: string, name: "approve" | "reject" | "archive" | "delete") {
    const reason = name === "reject" ? window.prompt("سبب الرفض؟") || "Rejected by reviewer" : "Governance action from admin UI";
    try {
      if (name === "delete") await api.delete(`/v1/knowledge-hub/documents/${documentId}`);
      else await api.post(`/v1/knowledge-hub/documents/${documentId}/${name}`, { reason });
      await load();
    } catch {
      setError("فشلت العملية. تأكد من امتلاكك الدور المناسب في Keycloak.");
    }
  }

  return (
    <AppShell>
      <main className="space-y-6 overflow-x-hidden bg-slate-50 p-4 text-slate-950 sm:p-6">
        <section className="rounded-3xl bg-primary-black p-6 text-white shadow-xl">
          <p className="text-sm font-semibold text-primary-gold">Knowledge Governance</p>
          <h1 className="mt-2 text-2xl font-bold sm:text-3xl">حوكمة المعرفة والوثائق</h1>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-300">إدارة دورة حياة الوثائق، الموافقات، الحساسية، الأرشفة، وحذف المتجهات من Qdrant ضمن صلاحيات Keycloak.</p>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {cards.map(([label, value]) => (
            <div key={String(label)} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">{label}</p>
              <p className="mt-2 text-3xl font-bold text-text-primary">{String(value)}</p>
            </div>
          ))}
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-lg font-bold">قائمة الوثائق</h2>
              <p className="text-sm text-slate-500">فلترة حسب الحالة مع أزرار الاعتماد والرفض والأرشفة والحذف.</p>
            </div>
            <select className="rounded-xl border border-slate-300 px-3 py-2 text-sm" value={filter} onChange={(e) => setFilter(e.target.value)}>
              {['all','draft','pending_review','approved','rejected','archived'].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {loading && <div className="mt-6 grid gap-3">{[1,2,3].map((i)=><div key={i} className="h-16 animate-pulse rounded-2xl bg-slate-100" />)}</div>}
          {error && <div className="mt-4 rounded-2xl bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}
          {!loading && rows.length === 0 && <div className="mt-6 rounded-2xl border border-dashed border-slate-300 p-8 text-center text-slate-500">لا توجد وثائق مطابقة للفلتر الحالي.</div>}

          {!loading && rows.length > 0 && (
            <div className="mt-6 overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-4 py-3 text-right">الوثيقة</th>
                    <th className="px-4 py-3 text-right">الحالة</th>
                    <th className="px-4 py-3 text-right">الحساسية</th>
                    <th className="px-4 py-3 text-right">القسم</th>
                    <th className="px-4 py-3 text-right">الإجراءات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((d) => (
                    <tr key={d.document_id} className="hover:bg-slate-50">
                      <td className="px-4 py-4"><div className="font-semibold text-slate-900">{d.title || d.filename}</div><div className="text-xs text-slate-500">{d.document_id}</div></td>
                      <td className="px-4 py-4"><StatusBadge status={d.status} /></td>
                      <td className="px-4 py-4">{d.sensitivity || d.classification || "internal"}</td>
                      <td className="px-4 py-4">{d.department || "general"}</td>
                      <td className="px-4 py-4">
                        <div className="flex flex-wrap gap-2">
                          {canReview && <button onClick={() => action(d.document_id, "approve")} className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-semibold text-white">Approve</button>}
                          {canReview && <button onClick={() => action(d.document_id, "reject")} className="rounded-lg bg-rose-600 px-3 py-1 text-xs font-semibold text-white">Reject</button>}
                          {canReview && <button onClick={() => action(d.document_id, "archive")} className="rounded-lg bg-slate-700 px-3 py-1 text-xs font-semibold text-white">Archive</button>}
                          {canDelete && <button onClick={() => action(d.document_id, "delete")} className="rounded-lg border border-rose-300 px-3 py-1 text-xs font-semibold text-rose-700">Delete</button>}
                          <a href={`/admin/knowledge-governance?document=${d.document_id}`} className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700">Audit Trail</a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </AppShell>
  );
}
