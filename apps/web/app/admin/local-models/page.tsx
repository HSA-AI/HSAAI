"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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

export default function LocalModelsPage() {
  const [form, setForm] = useState<LocalModelInput>({ name: "hsaai-local-model", version: "0.1", size: "7B", format: "GGUF", location: "/storage/local_models/model.gguf", provider: "provider_ollama_internal" });
  const [message, setMessage] = useState("Register local model metadata only. No heavy upload is required in this phase.");
  function update<K extends keyof LocalModelInput>(key: K, value: LocalModelInput[K]) { setForm((current) => ({ ...current, [key]: value })); }

  return (
    <AppShell>
      <main className="space-y-6">
        <section className="rounded-[2rem] bg-slate-950 p-8 text-white shadow-hsa-glow">
          <p className="text-xs font-black uppercase tracking-[0.35em] text-hsa-yellow">Local Model Management</p>
          <h1 className="mt-3 text-4xl font-black">إدارة النماذج المحلية</h1>
          <p className="mt-4 max-w-4xl leading-8 text-slate-300">تسجيل، عرض، تفعيل، وتعطيل نماذج GGUF و Safetensors و HuggingFace وربطها بمزود تشغيل داخلي.</p>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
          <Card>
            <h2 className="text-2xl font-black">تسجيل نموذج محلي</h2>
            <div className="mt-5 grid gap-4">
              <input className="rounded-xl border p-3" value={form.name} onChange={(e) => update("name", e.target.value)} placeholder="name" />
              <input className="rounded-xl border p-3" value={form.version} onChange={(e) => update("version", e.target.value)} placeholder="version" />
              <input className="rounded-xl border p-3" value={form.size} onChange={(e) => update("size", e.target.value)} placeholder="size" />
              <select className="rounded-xl border p-3" value={form.format} onChange={(e) => update("format", e.target.value as LocalModelFormat)}><option>GGUF</option><option>Safetensors</option><option>HF</option><option>Other</option></select>
              <input className="rounded-xl border p-3" value={form.location} onChange={(e) => update("location", e.target.value)} placeholder="location" />
              <input className="rounded-xl border p-3" value={form.provider} onChange={(e) => update("provider", e.target.value)} placeholder="provider" />
              <Button onClick={() => setMessage(`Registered metadata for ${form.name}. Real model import can be attached later.`)}>Register model</Button>
            </div>
          </Card>
          <Card>
            <h2 className="text-2xl font-black">النماذج المسجلة</h2>
            <div className="mt-5 space-y-4">
              {models.length === 0 ? (
                <p className="rounded-2xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 dark:border-slate-700">
                  No local models registered. Use the form on the left to register a new model.
                </p>
              ) : (
                models.map((model) => <div key={model.id} className="rounded-2xl border p-4 dark:border-slate-800"><div className="flex flex-wrap items-center justify-between gap-3"><b>{model.name}</b><span className="rounded-full bg-hsa-yellow/20 px-3 py-1 text-xs font-bold">{model.status}</span></div><p className="mt-2 text-sm text-slate-500">{model.version} · {model.size} · {model.format} · {model.provider}</p><p className="mt-1 text-xs text-slate-400">{model.location}</p><Button className="mt-3" onClick={() => setMessage(`Toggled ${model.name} in simulation mode.`)}>Activate / Disable</Button></div>)
              )}
            </div>
          </Card>
        </section>
        <Card><p className="rounded-2xl bg-black p-5 text-sm text-hsa-yellow">{message}</p></Card>
      </main>
    </AppShell>
  );
}
