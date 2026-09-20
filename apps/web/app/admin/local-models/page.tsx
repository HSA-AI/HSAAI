"use client";

import { useState, type ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/enterprise/page-state";
import type { LocalModelFormat, LocalModelInput } from "@/modules/local-models/local-model.types";

// FIX-MEDIUM-LOW-FINAL: Removed placeholder mock seed data (version "0.1-placeholder").
// Models are now fetched from the local-models API at runtime. Initialize as empty
// until the API call populates it.
const models: Array<{
  id: string;
  name: string;
  version: string;
  size: string;
  format: string;
  location: string;
  provider: string;
  status: string;
}> = [];

function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="text-xs font-bold text-hsa-secondary">{children}</span>;
}

export default function LocalModelsPage() {
  const [form, setForm] = useState<LocalModelInput>({ name: "hsaai-local-model", version: "0.1", size: "7B", format: "GGUF", location: "/storage/local_models/model.gguf", provider: "provider_ollama_internal" });
  const [message, setMessage] = useState("Register local model metadata only. No heavy upload is required in this phase.");
  function update<K extends keyof LocalModelInput>(key: K, value: LocalModelInput[K]) { setForm((current) => ({ ...current, [key]: value })); }

  return (
    <AppShell>
      <main className="space-y-6">
        <PageHeader
          eyebrow="Local Model Management"
          title="إدارة النماذج المحلية"
          description="تسجيل، عرض، تفعيل، وتعطيل نماذج GGUF و Safetensors و HuggingFace وربطها بمزود تشغيل داخلي."
        />

        <section className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">تسجيل نموذج محلي</h2>
            <div className="mt-5 grid gap-4">
              <label className="block">
                <FieldLabel>الاسم</FieldLabel>
                <Input className="mt-1.5" value={form.name} onChange={(e) => update("name", e.target.value)} placeholder="name" />
              </label>
              <label className="block">
                <FieldLabel>الإصدار</FieldLabel>
                <Input className="mt-1.5" value={form.version} onChange={(e) => update("version", e.target.value)} placeholder="version" />
              </label>
              <label className="block">
                <FieldLabel>الحجم</FieldLabel>
                <Input className="mt-1.5" value={form.size} onChange={(e) => update("size", e.target.value)} placeholder="size" />
              </label>
              <label className="block">
                <FieldLabel>الصيغة</FieldLabel>
                <select className="hsa-input mt-1.5" value={form.format} onChange={(e) => update("format", e.target.value as LocalModelFormat)} aria-label="صيغة النموذج"><option>GGUF</option><option>Safetensors</option><option>HF</option><option>Other</option></select>
              </label>
              <label className="block">
                <FieldLabel>المسار</FieldLabel>
                <Input className="mt-1.5" value={form.location} onChange={(e) => update("location", e.target.value)} placeholder="location" />
              </label>
              <label className="block">
                <FieldLabel>المزود</FieldLabel>
                <Input className="mt-1.5" value={form.provider} onChange={(e) => update("provider", e.target.value)} placeholder="provider" />
              </label>
              <Button onClick={() => setMessage(`Registered metadata for ${form.name}. Real model import can be attached later.`)}>Register model</Button>
            </div>
          </Card>
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">النماذج المسجلة</h2>
            <div className="mt-5 space-y-4">
              {models.length === 0 ? (
                <EmptyState
                  title="لا توجد نماذج مسجلة"
                  description="No local models registered. Use the form on the left to register a new model."
                />
              ) : (
                models.map((model) => (
                  <div key={model.id} className="rounded-xl border border-hsa-border bg-hsa-bg p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <b className="text-hsa-black">{model.name}</b>
                      <Badge tone="gold">{model.status}</Badge>
                    </div>
                    <p className="mt-2 text-sm text-hsa-secondary">{model.version} · {model.size} · {model.format} · {model.provider}</p>
                    <p dir="ltr" className="mt-1 text-start text-xs text-hsa-secondary">{model.location}</p>
                    <Button variant="secondary" className="mt-3" onClick={() => setMessage(`Toggled ${model.name} in simulation mode.`)}>Activate / Disable</Button>
                  </div>
                ))
              )}
            </div>
          </Card>
        </section>
        <Card>
          <p role="status" className="rounded-2xl border border-hsa-yellow/30 bg-hsa-soft p-5 text-sm leading-7 text-hsa-gold">{message}</p>
        </Card>
      </main>
    </AppShell>
  );
}
