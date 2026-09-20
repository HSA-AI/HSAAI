
"use client";
import { useEffect, useMemo, useState } from "react";
import { Activity, FileText, FolderTree, Layers } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/ui/kpi-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/enterprise/page-state";

type Space = { key: string; name: string; description: string; owner: string; classification: string; is_active: boolean };
type Collection = { key: string; name: string; space_key: string; description: string; document_count: number };
type DocumentRow = { document_id: string; filename: string; title: string; space_key: string; collection_key: string; version: number; status: string; classification: string; size_bytes: number; uploaded_by: string };

async function jsonFetch(path: string, init?: RequestInit) {
  const res = await fetch(path, { cache: "no-store", ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

const kpiIcons = [<FolderTree size={20} key="i0" />, <Layers size={20} key="i1" />, <FileText size={20} key="i2" />, <Activity size={20} key="i3" />];

export default function KnowledgeHubPage() {
  const [overview, setOverview] = useState<any>(null);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<DocumentRow[]>([]);
  const [spaceForm, setSpaceForm] = useState({ key: "", name: "", description: "", owner: "AI Admin", classification: "internal" });
  const [docForm, setDocForm] = useState({ space_key: "corporate", collection_key: "policies", filename: "", title: "", content_type: "application/pdf", size_bytes: 0, classification: "internal", metadata: {} as Record<string, string> });
  const spaces: Space[] = overview?.spaces || [];
  const collections: Collection[] = overview?.collections || [];
  const analytics = useMemo(() => overview?.analytics || {}, [overview]);

  async function load() {
    const data = await jsonFetch("/api/knowledge-hub/overview");
    setOverview(data);
    const docs = await jsonFetch("/api/knowledge-hub/documents");
    setDocuments(docs || []);
  }
  useEffect(() => { load().catch(console.error); }, []);

  async function createSpace() {
    await jsonFetch("/api/knowledge-hub/spaces", { method: "POST", body: JSON.stringify(spaceForm) });
    setSpaceForm({ key: "", name: "", description: "", owner: "AI Admin", classification: "internal" });
    await load();
  }
  async function registerDocument() {
    await jsonFetch("/api/knowledge-hub/documents/register", { method: "POST", body: JSON.stringify(docForm) });
    setDocForm({ ...docForm, filename: "", title: "", size_bytes: 0, metadata: {} });
    await load();
  }
  async function runSearch() {
    const data = await jsonFetch("/api/knowledge-hub/search", { method: "POST", body: JSON.stringify({ query, limit: 20 }) });
    setSearchResults(data.results || []);
  }

  const cards = useMemo(() => [
    ["Knowledge Spaces", analytics.spaces ?? 0, "مساحات معرفة مفصولة حسب القسم أو الغرض"],
    ["Collections", analytics.collections ?? 0, "مجموعات وثائق داخل كل مساحة"],
    ["Documents", analytics.documents ?? 0, "وثائق مسجلة مع الإصدارات والميتا داتا"],
    ["Events", analytics.events ?? 0, "أحداث استخدام وبحث وتحديث"],
  ], [analytics]);

  return <AppShell>
    <div className="space-y-6">
      <PageHeader
        eyebrow="HSAAI Enterprise Knowledge Hub"
        title="مركز المعرفة المؤسسي"
        description="إدارة مساحات المعرفة، المجموعات، إصدارات الوثائق، الصلاحيات، التحليلات، وربطها مع RAG المحلي داخل المؤسسة بدون اعتماد على خدمات ذكاء اصطناعي خارجية."
      />

      <section aria-label="مؤشرات مركز المعرفة" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map(([label, value, desc], i) => <KpiCard key={label as string} label={label as string} value={String(value)} hint={desc as string} icon={kpiIcons[i]} />)}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <h2 className="hsa-section-title">إنشاء Knowledge Space</h2>
          <div className="mt-4 space-y-3">
            <Input placeholder="key مثل hr" value={spaceForm.key} onChange={e => setSpaceForm({ ...spaceForm, key: e.target.value })} aria-label="مفتاح المساحة" />
            <Input placeholder="الاسم" value={spaceForm.name} onChange={e => setSpaceForm({ ...spaceForm, name: e.target.value })} aria-label="اسم المساحة" />
            <Input placeholder="المالك" value={spaceForm.owner} onChange={e => setSpaceForm({ ...spaceForm, owner: e.target.value })} aria-label="مالك المساحة" />
            <Textarea placeholder="الوصف" value={spaceForm.description} onChange={e => setSpaceForm({ ...spaceForm, description: e.target.value })} aria-label="وصف المساحة" />
            <Button onClick={createSpace} className="w-full">حفظ المساحة</Button>
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <h2 className="hsa-section-title">Spaces & Collections</h2>
          {spaces.length === 0 ? (
            <div className="mt-4">
              <EmptyState title="لا توجد مساحات معرفة بعد" description="أنشئ أول Knowledge Space من النموذج المجاور لتصنيف وثائق المؤسسة حسب القسم أو الغرض." />
            </div>
          ) : (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {spaces.map(s => <div key={s.key} className="rounded-xl border border-hsa-border bg-hsa-bg p-4 transition hover:border-hsa-gold/40">
                <div className="flex items-center justify-between gap-3"><strong className="text-hsa-black">{s.name}</strong><Badge tone="gold">{s.classification}</Badge></div>
                <p className="mt-2 text-xs leading-6 text-hsa-secondary">{s.description}</p>
                <p className="mt-2 text-xs text-hsa-secondary/80" dir="ltr">key: {s.key} · owner: {s.owner}</p>
              </div>)}
            </div>
          )}
          {collections.length > 0 && (
            <div className="mt-5 grid gap-2 md:grid-cols-2">
              {collections.map(c => <div key={`${c.space_key}-${c.key}`} className="rounded-xl border border-hsa-border bg-white p-3 text-sm text-hsa-black shadow-hsa-card">{c.name} <span className="text-xs text-hsa-secondary" dir="ltr">({c.space_key}/{c.key}) · {c.document_count || 0} docs</span></div>)}
            </div>
          )}
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="hsa-section-title">تسجيل وثيقة في مركز المعرفة</h2>
          <p className="mt-3 text-xs leading-6 text-hsa-secondary">هذا يسجل Metadata وVersion وPermissions. الفهرسة الدلالية الفعلية تبقى عبر RAG Engine.</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Input placeholder="space_key" value={docForm.space_key} onChange={e => setDocForm({ ...docForm, space_key: e.target.value })} aria-label="مفتاح المساحة للوثيقة" />
            <Input placeholder="collection_key" value={docForm.collection_key} onChange={e => setDocForm({ ...docForm, collection_key: e.target.value })} aria-label="مفتاح المجموعة للوثيقة" />
            <Input placeholder="filename.pdf" value={docForm.filename} onChange={e => setDocForm({ ...docForm, filename: e.target.value })} aria-label="اسم الملف" />
            <Input placeholder="title" value={docForm.title} onChange={e => setDocForm({ ...docForm, title: e.target.value })} aria-label="عنوان الوثيقة" />
            <Input placeholder="content type" value={docForm.content_type} onChange={e => setDocForm({ ...docForm, content_type: e.target.value })} aria-label="نوع المحتوى" />
            <Input type="number" placeholder="size bytes" value={docForm.size_bytes} onChange={e => setDocForm({ ...docForm, size_bytes: Number(e.target.value) })} aria-label="حجم الملف بالبايت" />
          </div>
          <Button onClick={registerDocument} className="mt-4">تسجيل الوثيقة</Button>
        </Card>
        <Card>
          <h2 className="hsa-section-title">بحث Metadata داخلي</h2>
          <div className="mt-4 flex gap-2"><Input value={query} onChange={e => setQuery(e.target.value)} placeholder="ابحث باسم الملف أو العنوان أو الميتاداتا" aria-label="كلمة البحث في الميتاداتا" /><Button onClick={runSearch}>بحث</Button></div>
          <div className="mt-4 space-y-2">
            {searchResults.length === 0 ? (
              <EmptyState title="لا توجد نتائج بعد" description="أدخل كلمة بحث ثم اضغط «بحث» لعرض الوثائق المطابقة من مركز المعرفة المؤسسي." />
            ) : searchResults.map(r => <div key={r.document_id} className="rounded-xl border border-hsa-border bg-hsa-bg p-3 text-sm transition hover:border-hsa-gold/40"><strong className="text-hsa-black">{r.title || r.filename}</strong><p className="mt-1 text-xs text-hsa-secondary" dir="ltr">{r.document_id} · v{r.version} · {r.classification}</p></div>)}
          </div>
        </Card>
      </section>

      <section className="rounded-xl border border-hsa-border bg-white p-5 shadow-hsa-card">
        <h2 className="hsa-section-title">Document Registry</h2>
        <div className="mt-4 overflow-x-auto"><table className="hsa-table min-w-[900px]"><thead><tr><th>Document</th><th>Space</th><th>Collection</th><th>Version</th><th>Status</th><th>Owner</th></tr></thead><tbody>{documents.map(d => <tr key={d.document_id}><td><strong className="text-hsa-black">{d.title || d.filename}</strong><p className="text-xs text-hsa-secondary" dir="ltr">{d.document_id}</p></td><td dir="ltr">{d.space_key}</td><td dir="ltr">{d.collection_key}</td><td dir="ltr">v{d.version}</td><td><Badge tone={d.status === "indexed" ? "ok" : d.status === "pending" ? "warn" : "neutral"}>{d.status}</Badge></td><td>{d.uploaded_by}</td></tr>)}</tbody></table></div>
      </section>
    </div>
  </AppShell>;
}
