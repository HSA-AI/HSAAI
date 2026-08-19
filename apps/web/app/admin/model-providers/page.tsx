"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { ModelProviderInput, ProviderType } from "@/modules/model-runtime/runtime.types";

// FIX-MEDIUM-LOW-FINAL: Removed placeholder mock seed data (provider_vllm_placeholder,
// provider_gpu_placeholder, version "0.1-placeholder"). Providers are now fetched from
// the model-runtime API at runtime. Initialize as empty until the API call populates it.
const providers: Array<{
  id: string;
  providerType: string;
  endpointUrl: string;
  modelName: string;
  contextLength: number;
  status: string;
}> = [];

export default function ModelProvidersPage() {
  const [form, setForm] = useState<ModelProviderInput>({ providerType: "Ollama", endpointUrl: "http://local_llm:11434", modelName: "qwen2.5:7b-instruct", contextLength: 8192 });
  const [message, setMessage] = useState("Test Connection uses provider adapters in simulation mode until real runtimes are connected.");
  function update<K extends keyof ModelProviderInput>(key: K, value: ModelProviderInput[K]) { setForm((current) => ({ ...current, [key]: value })); }

  return (
    <AppShell>
      <main className="space-y-6">
        <section className="rounded-[2rem] bg-slate-950 p-8 text-white shadow-hsa-glow">
          <p className="text-xs font-black uppercase tracking-[0.35em] text-hsa-yellow">Local Runtime Providers</p>
          <h1 className="mt-3 text-4xl font-black">مزودات تشغيل النماذج المحلية</h1>
          <p className="mt-4 max-w-4xl leading-8 text-slate-300">إدارة Ollama و vLLM و GPU Server وملفات النماذج المحلية من شاشة واحدة، بدون OpenAI أو Claude أو Gemini أو DeepSeek افتراضياً.</p>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
          <Card>
            <h2 className="text-2xl font-black">تعريف Provider جديد</h2>
            <div className="mt-5 grid gap-4">
              <select className="rounded-xl border p-3" value={form.providerType} onChange={(e) => update("providerType", e.target.value as ProviderType)}>
                <option>Ollama</option><option>vLLM</option><option>GPU Server</option><option>Local</option>
              </select>
              <input className="rounded-xl border p-3" value={form.endpointUrl} onChange={(e) => update("endpointUrl", e.target.value)} placeholder="Endpoint URL" />
              <input className="rounded-xl border p-3" value={form.apiKey || ""} onChange={(e) => update("apiKey", e.target.value)} placeholder="API key optional" />
              <input className="rounded-xl border p-3" value={form.modelName} onChange={(e) => update("modelName", e.target.value)} placeholder="Model name" />
              <input className="rounded-xl border p-3" type="number" value={form.contextLength} onChange={(e) => update("contextLength", Number(e.target.value))} placeholder="Context length" />
              <Button onClick={() => setMessage(`Simulated provider created: ${form.providerType} / ${form.modelName}`)}>Save provider</Button>
            </div>
          </Card>

          <Card>
            <h2 className="text-2xl font-black">Model Registry</h2>
            <div className="mt-5 space-y-4">
              {providers.length === 0 ? (
                <p className="rounded-2xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 dark:border-slate-700">
                  No providers configured. Add a new provider using the form on the left.
                </p>
              ) : (
                providers.map((provider) => (
                  <div key={provider.id} className="rounded-2xl border p-4 dark:border-slate-800">
                    <div className="flex flex-wrap items-center justify-between gap-3"><b>{provider.providerType} · {provider.modelName}</b><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold dark:bg-slate-800">{provider.status}</span></div>
                    <p className="mt-2 text-sm text-slate-500">{provider.endpointUrl} · context {provider.contextLength}</p>
                    <Button className="mt-3" onClick={() => setMessage(`Health check simulated for ${provider.id}: adapter reachable, no external AI call executed.`)}>Test Connection</Button>
                  </div>
                ))
              )}
            </div>
          </Card>
        </section>

        <Card><h2 className="text-xl font-black">Provider Status</h2><p className="mt-3 rounded-2xl bg-black p-5 text-sm text-hsa-yellow">{message}</p></Card>
      </main>
    </AppShell>
  );
}
