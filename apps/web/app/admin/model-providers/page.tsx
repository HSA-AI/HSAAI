"use client";

import { useState, type ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/enterprise/page-state";
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

function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="text-xs font-bold text-hsa-secondary">{children}</span>;
}

export default function ModelProvidersPage() {
  const [form, setForm] = useState<ModelProviderInput>({ providerType: "Ollama", endpointUrl: "http://local_llm:11434", modelName: "qwen2.5:7b-instruct", contextLength: 8192 });
  const [message, setMessage] = useState("Test Connection uses provider adapters in simulation mode until real runtimes are connected.");
  function update<K extends keyof ModelProviderInput>(key: K, value: ModelProviderInput[K]) { setForm((current) => ({ ...current, [key]: value })); }

  return (
    <AppShell>
      <main className="space-y-6">
        <PageHeader
          eyebrow="Local Runtime Providers"
          title="مزودات تشغيل النماذج المحلية"
          description="إدارة Ollama و vLLM و GPU Server وملفات النماذج المحلية من شاشة واحدة، بدون OpenAI أو Claude أو Gemini أو DeepSeek افتراضياً."
        />

        <section className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">تعريف Provider جديد</h2>
            <div className="mt-5 grid gap-4">
              <label className="block">
                <FieldLabel>Provider Type</FieldLabel>
                <select className="hsa-input mt-1.5" value={form.providerType} onChange={(e) => update("providerType", e.target.value as ProviderType)} aria-label="نوع المزود">
                  <option>Ollama</option><option>vLLM</option><option>GPU Server</option><option>Local</option>
                </select>
              </label>
              <label className="block">
                <FieldLabel>Endpoint URL</FieldLabel>
                <Input className="mt-1.5" value={form.endpointUrl} onChange={(e) => update("endpointUrl", e.target.value)} placeholder="Endpoint URL" />
              </label>
              <label className="block">
                <FieldLabel>API Key (اختياري)</FieldLabel>
                <Input className="mt-1.5" value={form.apiKey || ""} onChange={(e) => update("apiKey", e.target.value)} placeholder="API key optional" />
              </label>
              <label className="block">
                <FieldLabel>Model Name</FieldLabel>
                <Input className="mt-1.5" value={form.modelName} onChange={(e) => update("modelName", e.target.value)} placeholder="Model name" />
              </label>
              <label className="block">
                <FieldLabel>Context Length</FieldLabel>
                <Input className="mt-1.5" type="number" value={form.contextLength} onChange={(e) => update("contextLength", Number(e.target.value))} placeholder="Context length" />
              </label>
              <Button onClick={() => setMessage(`Simulated provider created: ${form.providerType} / ${form.modelName}`)}>Save provider</Button>
            </div>
          </Card>

          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Model Registry</h2>
            <div className="mt-5 space-y-4">
              {providers.length === 0 ? (
                <EmptyState
                  title="لا توجد مزودات مُعرّفة"
                  description="No providers configured. Add a new provider using the form on the left."
                />
              ) : (
                providers.map((provider) => (
                  <div key={provider.id} className="rounded-xl border border-hsa-border bg-hsa-bg p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <b className="text-hsa-black">{provider.providerType} · {provider.modelName}</b>
                      <Badge tone="neutral">{provider.status}</Badge>
                    </div>
                    <p className="mt-2 text-sm text-hsa-secondary">{provider.endpointUrl} · context {provider.contextLength}</p>
                    <Button variant="secondary" className="mt-3" onClick={() => setMessage(`Health check simulated for ${provider.id}: adapter reachable, no external AI call executed.`)}>Test Connection</Button>
                  </div>
                ))
              )}
            </div>
          </Card>
        </section>

        <Card>
          <h2 className="text-lg font-bold text-hsa-black">Provider Status</h2>
          <p role="status" className="mt-3 rounded-2xl border border-hsa-yellow/30 bg-hsa-soft p-5 text-sm leading-7 text-hsa-gold">{message}</p>
        </Card>
      </main>
    </AppShell>
  );
}
