"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { KpiCard } from "@/components/ui/kpi-card";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/enterprise/page-state";
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

const statusTone: Record<string, "ok" | "warn" | "error" | "neutral" | "info"> = {
  approved: "ok",
  pending_review: "warn",
  rejected: "error",
  archived: "neutral",
  draft: "info",
};

function StatusBadge({ status }: { status: string }) {
  return <Badge tone={statusTone[status] || statusTone.draft}>{status}</Badge>;
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
      <main className="space-y-6">
        <PageHeader
          eyebrow="Knowledge Governance"
          title="حوكمة المعرفة والوثائق"
          description="إدارة دورة حياة الوثائق، الموافقات، الحساسية، الأرشفة، وحذف المتجهات من Qdrant ضمن صلاحيات Keycloak."
        />

        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {cards.map(([label, value]) => (
            <KpiCard key={String(label)} label={String(label)} value={String(value)} />
          ))}
        </section>

        <Card>
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-lg font-bold text-hsa-black">قائمة الوثائق</h2>
              <p className="text-sm text-hsa-secondary">فلترة حسب الحالة مع أزرار الاعتماد والرفض والأرشفة والحذف.</p>
            </div>
            <select className="hsa-input w-auto text-sm" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="فلترة حسب الحالة">
              {['all','draft','pending_review','approved','rejected','archived'].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {loading && <div className="mt-6"><LoadingState /></div>}
          {error && <div className="mt-4"><ErrorState description={error} /></div>}
          {!loading && rows.length === 0 && (
            <div className="mt-6">
              <EmptyState title="لا توجد وثائق" description="لا توجد وثائق مطابقة للفلتر الحالي." />
            </div>
          )}

          {!loading && rows.length > 0 && (
            <div className="mt-6 overflow-x-auto">
              <table className="hsa-table min-w-[760px]">
                <thead>
                  <tr>
                    <th>الوثيقة</th>
                    <th>الحالة</th>
                    <th>الحساسية</th>
                    <th>القسم</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((d) => (
                    <tr key={d.document_id}>
                      <td><div className="font-bold text-hsa-black">{d.title || d.filename}</div><div dir="ltr" className="mt-1 text-start text-xs text-hsa-secondary">{d.document_id}</div></td>
                      <td><StatusBadge status={d.status} /></td>
                      <td>{d.sensitivity || d.classification || "internal"}</td>
                      <td>{d.department || "general"}</td>
                      <td>
                        <div className="flex flex-wrap gap-2">
                          {canReview && <Button variant="secondary" className="px-3 py-1 text-xs font-bold text-emerald-700 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700" onClick={() => action(d.document_id, "approve")}>Approve</Button>}
                          {canReview && <Button variant="secondary" className="px-3 py-1 text-xs font-bold text-rose-700 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700" onClick={() => action(d.document_id, "reject")}>Reject</Button>}
                          {canReview && <Button variant="secondary" className="px-3 py-1 text-xs" onClick={() => action(d.document_id, "archive")}>Archive</Button>}
                          {canDelete && <Button variant="secondary" className="px-3 py-1 text-xs font-bold text-red-700 hover:border-red-300 hover:bg-red-50 hover:text-red-700" onClick={() => action(d.document_id, "delete")}>Delete</Button>}
                          <a href={`/admin/knowledge-governance?document=${d.document_id}`} className="inline-flex items-center rounded-xl border border-hsa-border bg-white px-3 py-1 text-xs font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft">Audit Trail</a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </AppShell>
  );
}
