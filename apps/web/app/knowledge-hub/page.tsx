
"use client";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type Space = { key: string; name: string; description: string; owner: string; classification: string; is_active: boolean };
type Collection = { key: string; name: string; space_key: string; description: string; document_count: number };
type DocumentRow = { document_id: string; filename: string; title: string; space_key: string; collection_key: string; version: number; status: string; classification: string; size_bytes: number; uploaded_by: string };

// FIX V3: Use enterprise safeFetch instead of raw fetch with response.text()
// Previously this helper captured entire HTML pages as error messages.
import { apiGet, apiPost, apiPut, apiDelete, type ApiError } from "@/lib/safe-fetch";

async function jsonFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const body = init?.body ? JSON.parse(init.body as string) : undefined;

  let result;
  if (method === "GET") result = await apiGet(path);
  else if (method === "POST") result = await apiPost(path, body);
  else if (method === "PUT") result = await apiPut(path, body);
  else if (method === "DELETE") result = await apiDelete(path);
  else result = await apiGet(path);

  if (result.error) throw new Error(result.error.message);
  return result.data as T;
}

export default function KnowledgeHubPage() {
  const [overview, setOverview] = useState<any>(null);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<DocumentRow[]>([]);
  const [spaceForm, setSpaceForm] = useState({ key: "", name: "", description: "", owner: "AI Admin", classification: "internal" });
  const [docForm, setDocForm] = useState({ space_key: "corporate", collection_key: "policies", filename: "", title: "", content_type: "application/pdf", size_bytes: 0, classification: "internal", metadata: {} as Record<string, string> });
  const spaces: Space[] = overview?.spaces || [];
  const collections: Collection[] = overview?.collections || [];
  const analytics = overview?.analytics || {};

  async function load() {
    const data: any = await jsonFetch("/api/knowledge-hub/overview");
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
    const data: any = await jsonFetch("/api/knowledge-hub/search", { method: "POST", body: JSON.stringify({ query, limit: 20 }) });
    setSearchResults(data.results || []);
  }

  const cards = useMemo(() => [
    ["Knowledge Spaces", analytics.spaces ?? 0, "مساحات معرفة مفصولة حسب القسم أو الغرض"],
    ["Collections", analytics.collections ?? 0, "مجموعات وثائق داخل كل مساحة"],
    ["Documents", analytics.documents ?? 0, "وثائق مسجلة مع الإصدارات والميتا داتا"],
    ["Events", analytics.events ?? 0, "أحداث استخدام وبحث وتحديث"],
  ], [analytics]);

  return <AppShell>
    <main className="space-y-6">
      <section className="rounded-3xl border border-hsa-yellow/20 bg-gradient-to-br from-slate-950 to-slate-900 p-6 shadow-2xl">
        <p className="text-sm font-bold text-hsa-yellow">HSAAI Enterprise Knowledge Hub</p>
        <h1 className="mt-2 text-3xl font-black text-white">مركز المعرفة المؤسسي</h1>
        <p className="mt-3 max-w-4xl leading-7 text-slate-300">إدارة مساحات المعرفة، المجموعات، إصدارات الوثائق، الصلاحيات، التحليلات، وربطها مع RAG المحلي داخل المؤسسة بدون اعتماد على خدمات ذكاء اصطناعي خارجية.</p>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        {cards.map(([label, value, desc]) => <div key={label as string} className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
          <strong className="mt-2 block text-3xl font-black text-white">{String(value)}</strong>
          <p className="mt-2 text-xs leading-6 text-slate-400">{desc}</p>
        </div>)}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-800 bg-slate-950 p-5 lg:col-span-1">
          <h2 className="font-bold text-white">إنشاء Knowledge Space</h2>
          <div className="mt-4 space-y-3">
            <Input placeholder="key مثل hr" value={spaceForm.key} onChange={e => setSpaceForm({ ...spaceForm, key: e.target.value })} />
            <Input placeholder="الاسم" value={spaceForm.name} onChange={e => setSpaceForm({ ...spaceForm, name: e.target.value })} />
            <Input placeholder="المالك" value={spaceForm.owner} onChange={e => setSpaceForm({ ...spaceForm, owner: e.target.value })} />
            <Textarea placeholder="الوصف" value={spaceForm.description} onChange={e => setSpaceForm({ ...spaceForm, description: e.target.value })} />
            <Button onClick={createSpace} className="w-full">حفظ المساحة</Button>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950 p-5 lg:col-span-2">
          <h2 className="font-bold text-white">Spaces & Collections</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {spaces.map(s => <div key={s.key} className="rounded-xl border border-hsa-yellow/20 bg-black/30 p-4">
              <div className="flex items-center justify-between gap-3"><strong className="text-white">{s.name}</strong><span className="rounded-full bg-hsa-yellow/10 px-2 py-1 text-xs text-hsa-yellow">{s.classification}</span></div>
              <p className="mt-2 text-xs leading-6 text-slate-400">{s.description}</p>
              <p className="mt-2 text-xs text-slate-500">key: {s.key} · owner: {s.owner}</p>
            </div>)}
          </div>
          <div className="mt-5 grid gap-2 md:grid-cols-2">
            {collections.map(c => <div key={`${c.space_key}-${c.key}`} className="rounded-xl bg-slate-900 p-3 text-sm text-slate-300">{c.name} <span className="text-xs text-slate-500">({c.space_key}/{c.key}) · {c.document_count || 0} docs</span></div>)}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="font-bold text-white">تسجيل وثيقة في مركز المعرفة</h2>
          <p className="mt-1 text-xs leading-6 text-slate-400">هذا يسجل Metadata وVersion وPermissions. الفهرسة الدلالية الفعلية تبقى عبر RAG Engine.</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Input placeholder="space_key" value={docForm.space_key} onChange={e => setDocForm({ ...docForm, space_key: e.target.value })} />
            <Input placeholder="collection_key" value={docForm.collection_key} onChange={e => setDocForm({ ...docForm, collection_key: e.target.value })} />
            <Input placeholder="filename.pdf" value={docForm.filename} onChange={e => setDocForm({ ...docForm, filename: e.target.value })} />
            <Input placeholder="title" value={docForm.title} onChange={e => setDocForm({ ...docForm, title: e.target.value })} />
            <Input placeholder="content type" value={docForm.content_type} onChange={e => setDocForm({ ...docForm, content_type: e.target.value })} />
            <Input type="number" placeholder="size bytes" value={docForm.size_bytes} onChange={e => setDocForm({ ...docForm, size_bytes: Number(e.target.value) })} />
          </div>
          <Button onClick={registerDocument} className="mt-4">تسجيل الوثيقة</Button>
        </div>
        <div className="rounded-2xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="font-bold text-white">بحث Metadata داخلي</h2>
          <div className="mt-4 flex gap-2"><Input value={query} onChange={e => setQuery(e.target.value)} placeholder="ابحث باسم الملف أو العنوان أو الميتاداتا" /><Button onClick={runSearch}>بحث</Button></div>
          <div className="mt-4 space-y-2">{searchResults.map(r => <div key={r.document_id} className="rounded-xl border border-hsa-yellow/20 bg-black/30 p-3 text-sm text-slate-300"><strong className="text-white">{r.title || r.filename}</strong><p className="text-xs text-slate-500">{r.document_id} · v{r.version} · {r.classification}</p></div>)}</div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-950 p-5">
        <h2 className="font-bold text-white">Document Registry</h2>
        <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="text-slate-500"><tr><th className="p-2 text-right">Document</th><th className="p-2 text-right">Space</th><th className="p-2 text-right">Collection</th><th className="p-2 text-right">Version</th><th className="p-2 text-right">Status</th><th className="p-2 text-right">Owner</th></tr></thead><tbody>{documents.map(d => <tr key={d.document_id} className="border-t border-slate-800 text-slate-300"><td className="p-2"><strong className="text-white">{d.title || d.filename}</strong><p className="text-xs text-slate-500">{d.document_id}</p></td><td className="p-2">{d.space_key}</td><td className="p-2">{d.collection_key}</td><td className="p-2">v{d.version}</td><td className="p-2">{d.status}</td><td className="p-2">{d.uploaded_by}</td></tr>)}</tbody></table></div>
      </section>
    </main>
  </AppShell>;
}
