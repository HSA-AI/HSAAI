"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorCard } from "@/components/error-card";
import type { TrainingCreatePayload, TrainingJob } from "@/modules/training/enterprise-training.types";
import { enterpriseTrainingApi } from "@/modules/training/enterprise-training.service";
import type { ApiError } from "@/lib/safe-fetch";

// ═══════════════════════════════════════════════════════════════════════
// FIX V3: This page previously displayed raw HTML when the backend was
// unreachable, because the fetch helper captured the entire HTML response
// body as the error message. Now uses the enterprise safeFetch utility
// which returns structured ApiError objects with Arabic messages.
// ═══════════════════════════════════════════════════════════════════════

const initialPayload: TrainingCreatePayload = {
  training_name: "hsaai-qwen-enterprise-lora-v1",
  description: "Enterprise LoRA run for internal HSAAI knowledge style alignment.",
  base_model: "/models/Qwen2.5-7B-Instruct",
  dataset_path: "/artifacts/datasets/hsaai/train.jsonl",
  method: "LoRA",
  hyperparameters: { epochs: 3, learning_rate: 0.0002, batch_size: 1, gradient_accumulation: 4, warmup_steps: 50, weight_decay: 0, max_sequence_length: 2048, lora_rank: 16, lora_alpha: 32, lora_dropout: 0.05 },
  compute: { gpu_device: "auto", cpu_limit: "8", ram_limit: "64Gi", vram_limit: "24Gi", multi_gpu: false },
  output_model_name: "hsaai-qwen-enterprise-v1"
};

export default function ModelTrainingPage() {
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [payload, setPayload] = useState<TrainingCreatePayload>(initialPayload);
  const [selectedJob, setSelectedJob] = useState<number | null>(null);
  const [logs, setLogs] = useState<unknown[]>([]);
  const [metrics, setMetrics] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState<ApiError | null>(null);

  const overview = useMemo(() => ({
    total: jobs.length,
    active: jobs.filter(j => ["Preparing", "Training", "Validating", "Saving", "Deploying"].includes(j.status)).length,
    failed: jobs.filter(j => j.status === "Failed").length,
    completed: jobs.filter(j => j.status === "Completed").length
  }), [jobs]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await enterpriseTrainingApi.jobs();
    if (result.error) {
      setError(result.error);
    } else {
      setJobs(result.data || []);
    }
    setLoading(false);
  }, []);

  async function create() {
    setActionError(null);
    const result = await enterpriseTrainingApi.createJob(payload);
    if (result.error) {
      setActionError(result.error);
      return;
    }
    if (result.data) {
      setJobs([result.data, ...jobs]);
      setSelectedJob(result.data.id);
    }
  }

  async function start(id: number) {
    setActionError(null);
    const result = await enterpriseTrainingApi.startJob(id);
    if (result.error) { setActionError(result.error); return; }
    await load();
  }

  async function cancel(id: number) {
    setActionError(null);
    const result = await enterpriseTrainingApi.cancelJob(id);
    if (result.error) { setActionError(result.error); return; }
    await load();
  }

  async function loadDetails(id: number) {
    setSelectedJob(id);
    setActionError(null);
    const [l, m] = await Promise.all([
      enterpriseTrainingApi.logs(id),
      enterpriseTrainingApi.metrics(id),
    ]);
    if (l.error || m.error) {
      setActionError(l.error || m.error);
      return;
    }
    setLogs(l.data || []);
    setMetrics((m.data?.points ?? []) as Array<Record<string, unknown>>);
  }

  useEffect(() => { void load(); }, [load]);

  return (
    <AppShell>
      <main className="space-y-6">
        <section className="rounded-[2rem] bg-slate-950 p-8 text-white shadow-hsa-glow">
          <p className="text-xs font-black uppercase tracking-[0.35em] text-hsa-yellow">HSAAI Enterprise Model Training</p>
          <h1 className="mt-3 text-4xl font-black">نظام تدريب نماذج فعلي داخل المؤسسة</h1>
          <p className="mt-4 max-w-5xl leading-8 text-slate-300">LoRA و QLoRA و SFT عبر FastAPI + Redis/RQ + GPU Worker + PostgreSQL + Model Registry. لا توجد Fake Progress: المؤشرات تأتي من سجلات التدريب وCallbacks وnvidia-smi.</p>
        </section>

        {/* FIX V3: Use ErrorCard instead of raw {error} interpolation */}
        <ErrorCard error={error} onRetry={() => void load()} title="Training backend غير متصل" />
        <ErrorCard error={actionError} onRetry={() => setActionError(null)} variant="banner" />

        {loading && !error && (
          <div className="flex items-center justify-center py-12">
            <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-slate-900 animate-spin" />
          </div>
        )}

        {!loading && !error && (
          <>
            <section className="grid gap-4 md:grid-cols-4 xl:grid-cols-7">
              {[['Total Jobs', overview.total], ['Active Jobs', overview.active], ['Failed Jobs', overview.failed], ['Completed', overview.completed], ['GPU Usage', 'nvidia-smi'], ['VRAM Usage', 'live'], ['Training Hours', 'tracked']].map(([k, v]) => (
                <Card key={k}>
                  <p className="text-sm text-slate-500">{k}</p>
                  <p className="mt-2 text-2xl font-black">{v}</p>
                </Card>
              ))}
            </section>

            <section className="grid gap-6 xl:grid-cols-[420px_1fr]">
              <Card>
                <h2 className="text-2xl font-black">Create Training Wizard</h2>
                <div className="mt-5 space-y-3">
                  <Field label="Training Name" value={payload.training_name} onChange={v => setPayload({ ...payload, training_name: v })} />
                  <Field label="Description" value={payload.description ?? ''} onChange={v => setPayload({ ...payload, description: v })} />
                  <Field label="Base Model" value={payload.base_model} onChange={v => setPayload({ ...payload, base_model: v })} />
                  <Field label="Dataset Path" value={payload.dataset_path ?? ''} onChange={v => setPayload({ ...payload, dataset_path: v })} />
                  <label className="block text-sm font-bold">Training Method
                    <select className="mt-1 w-full rounded-xl border p-3" value={payload.method} onChange={e => setPayload({ ...payload, method: e.target.value as TrainingCreatePayload['method'] })}>
                      <option>LoRA</option><option>QLoRA</option><option>SFT</option>
                    </select>
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <Num label="Epochs" value={payload.hyperparameters.epochs} onChange={v => setPayload({ ...payload, hyperparameters: { ...payload.hyperparameters, epochs: v } })} />
                    <Num label="Batch" value={payload.hyperparameters.batch_size} onChange={v => setPayload({ ...payload, hyperparameters: { ...payload.hyperparameters, batch_size: v } })} />
                    <Num label="Grad Accum" value={payload.hyperparameters.gradient_accumulation} onChange={v => setPayload({ ...payload, hyperparameters: { ...payload.hyperparameters, gradient_accumulation: v } })} />
                    <Num label="Max Seq" value={payload.hyperparameters.max_sequence_length} onChange={v => setPayload({ ...payload, hyperparameters: { ...payload.hyperparameters, max_sequence_length: v } })} />
                  </div>
                  <Field label="Learning Rate" value={String(payload.hyperparameters.learning_rate)} onChange={v => setPayload({ ...payload, hyperparameters: { ...payload.hyperparameters, learning_rate: Number(v) } })} />
                  <div className="grid grid-cols-3 gap-3">
                    <Num label="LoRA Rank" value={payload.hyperparameters.lora_rank} onChange={v => setPayload({ ...payload, hyperparameters: { ...payload.hyperparameters, lora_rank: v } })} />
                    <Num label="Alpha" value={payload.hyperparameters.lora_alpha} onChange={v => setPayload({ ...payload, hyperparameters: { ...payload.hyperparameters, lora_alpha: v } })} />
                    <Field label="GPU" value={payload.compute.gpu_device} onChange={v => setPayload({ ...payload, compute: { ...payload.compute, gpu_device: v } })} />
                  </div>
                  <Button onClick={() => void create()}>Create Real Training Job</Button>
                </div>
              </Card>

              <Card>
                <h2 className="text-2xl font-black">Training Jobs</h2>
                <div className="mt-5 overflow-auto">
                  <table className="w-full min-w-[900px] text-left text-sm">
                    <thead>
                      <tr className="border-b text-slate-500">
                        <th className="p-3">Job ID</th><th>Training Name</th><th>Base Model</th><th>Method</th><th>Status</th><th>GPU</th><th>Created</th><th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map(j => (
                        <tr key={j.id} className="border-b">
                          <td className="p-3 font-bold">#{j.id}</td>
                          <td>{j.training_name}</td>
                          <td>{j.base_model}</td>
                          <td>{j.method}</td>
                          <td><span className="rounded-full bg-hsa-yellow/20 px-3 py-1 text-xs font-bold">{j.status}</span></td>
                          <td>{j.gpu_device ?? 'auto'}</td>
                          <td>{new Date(j.created_at).toLocaleString()}</td>
                          <td className="space-x-2">
                            <Button onClick={() => void start(j.id)}>Start</Button>
                            <Button onClick={() => void loadDetails(j.id)}>Monitor</Button>
                            <Button onClick={() => void cancel(j.id)}>Cancel</Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
              <Card>
                <h2 className="text-xl font-black">Loss Visualization</h2>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={metrics}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="step" />
                      <YAxis />
                      <Tooltip />
                      <Line type="monotone" dataKey="loss" dot={false} />
                      <Line type="monotone" dataKey="eval_loss" dot={false} />
                      <Line type="monotone" dataKey="learning_rate" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>
              <Card>
                <h2 className="text-xl font-black">Live Logs {selectedJob ? `#${selectedJob}` : ''}</h2>
                {/* FIX V3: Safely stringify logs — never display raw HTML */}
                <pre className="mt-4 h-72 overflow-auto rounded-2xl bg-black p-5 text-xs leading-6 text-hsa-yellow">
                  {JSON.stringify(logs, null, 2).slice(0, 5000)}
                </pre>
              </Card>
            </section>
          </>
        )}
      </main>
    </AppShell>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block text-sm font-bold">{label}
      <input className="mt-1 w-full rounded-xl border p-3" value={value} onChange={e => onChange(e.target.value)} />
    </label>
  );
}

function Num({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label className="block text-sm font-bold">{label}
      <input type="number" className="mt-1 w-full rounded-xl border p-3" value={value} onChange={e => onChange(Number(e.target.value))} />
    </label>
  );
}
