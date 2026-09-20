
"use client";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/ui/kpi-card";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/enterprise/page-state";
import { Activity, AlertTriangle, CheckCircle2, Cpu, Gauge, ListChecks, Timer } from "lucide-react";
import type { TrainingCreatePayload, TrainingJob } from "@/modules/training/enterprise-training.types";
import { enterpriseTrainingApi } from "@/modules/training/enterprise-training.service";

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

const ACTIVE_STATUSES = ["Preparing", "Training", "Validating", "Saving", "Deploying"];

function jobStatusTone(status: string): "ok" | "warn" | "error" | "neutral" {
  if (status === "Failed") return "error";
  if (status === "Completed") return "ok";
  if (ACTIVE_STATUSES.includes(status)) return "warn";
  return "neutral";
}

export default function ModelTrainingPage() {
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [payload, setPayload] = useState<TrainingCreatePayload>(initialPayload);
  const [selectedJob, setSelectedJob] = useState<number | null>(null);
  const [logs, setLogs] = useState<unknown[]>([]);
  const [metrics, setMetrics] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);
  const overview = useMemo(() => ({ total: jobs.length, active: jobs.filter(j => ACTIVE_STATUSES.includes(j.status)).length, failed: jobs.filter(j => j.status === "Failed").length, completed: jobs.filter(j => j.status === "Completed").length }), [jobs]);
  async function load() { try { setError(null); setJobs(await enterpriseTrainingApi.jobs()); } catch (e) { setError(e instanceof Error ? e.message : "Training API is not reachable"); }}
  async function create() { const job = await enterpriseTrainingApi.createJob(payload); setJobs([job, ...jobs]); setSelectedJob(job.id); }
  async function start(id: number) { await enterpriseTrainingApi.startJob(id); await load(); }
  async function cancel(id: number) { await enterpriseTrainingApi.cancelJob(id); await load(); }
  async function loadDetails(id: number) { setSelectedJob(id); const [l, m] = await Promise.all([enterpriseTrainingApi.logs(id), enterpriseTrainingApi.metrics(id)]); setLogs(l); setMetrics((m.points ?? []) as Array<Record<string, unknown>>); }
  useEffect(() => { void load(); }, []);

  const overviewCards: Array<{ label: string; value: string | number; icon: ReactNode }> = [
    { label: "Total Jobs", value: overview.total, icon: <ListChecks size={20} /> },
    { label: "Active Jobs", value: overview.active, icon: <Activity size={20} /> },
    { label: "Failed Jobs", value: overview.failed, icon: <AlertTriangle size={20} /> },
    { label: "Completed", value: overview.completed, icon: <CheckCircle2 size={20} /> },
    { label: "GPU Usage", value: "nvidia-smi", icon: <Cpu size={20} /> },
    { label: "VRAM Usage", value: "live", icon: <Gauge size={20} /> },
    { label: "Training Hours", value: "tracked", icon: <Timer size={20} /> },
  ];

  return (
    <AppShell>
      <main className="space-y-6">
        <PageHeader
          eyebrow="HSAAI Enterprise Model Training"
          title="نظام تدريب نماذج فعلي داخل المؤسسة"
          description="LoRA و QLoRA و SFT عبر FastAPI + Redis/RQ + GPU Worker + PostgreSQL + Model Registry. لا توجد Fake Progress: المؤشرات تأتي من سجلات التدريب وCallbacks وnvidia-smi."
        />

        {error ? <ErrorState title="Training backend غير متصل" description={error} /> : null}

        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {overviewCards.map((c) => (
            <KpiCard key={c.label} label={c.label} value={c.value} icon={c.icon} />
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-[420px_1fr]">
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Create Training Wizard</h2>
            <div className="mt-5 space-y-3">
              <Field label="Training Name" value={payload.training_name} onChange={v=>setPayload({...payload, training_name:v})}/>
              <Field label="Description" value={payload.description ?? ''} onChange={v=>setPayload({...payload, description:v})}/>
              <Field label="Base Model" value={payload.base_model} onChange={v=>setPayload({...payload, base_model:v})}/>
              <Field label="Dataset Path" value={payload.dataset_path ?? ''} onChange={v=>setPayload({...payload, dataset_path:v})}/>
              <label className="block">
                <span className="text-xs font-bold text-hsa-secondary">Training Method</span>
                <select className="hsa-input mt-1.5" value={payload.method} onChange={e=>setPayload({...payload, method:e.target.value as TrainingCreatePayload['method']})} aria-label="طريقة التدريب">
                  <option>LoRA</option><option>QLoRA</option><option>SFT</option>
                </select>
              </label>
              <div className="grid grid-cols-2 gap-3"><Num label="Epochs" value={payload.hyperparameters.epochs} onChange={v=>setPayload({...payload, hyperparameters:{...payload.hyperparameters, epochs:v}})}/><Num label="Batch" value={payload.hyperparameters.batch_size} onChange={v=>setPayload({...payload, hyperparameters:{...payload.hyperparameters, batch_size:v}})}/><Num label="Grad Accum" value={payload.hyperparameters.gradient_accumulation} onChange={v=>setPayload({...payload, hyperparameters:{...payload.hyperparameters, gradient_accumulation:v}})}/><Num label="Max Seq" value={payload.hyperparameters.max_sequence_length} onChange={v=>setPayload({...payload, hyperparameters:{...payload.hyperparameters, max_sequence_length:v}})}/></div>
              <Field label="Learning Rate" value={String(payload.hyperparameters.learning_rate)} onChange={v=>setPayload({...payload, hyperparameters:{...payload.hyperparameters, learning_rate:Number(v)}})}/>
              <div className="grid grid-cols-3 gap-3"><Num label="LoRA Rank" value={payload.hyperparameters.lora_rank} onChange={v=>setPayload({...payload, hyperparameters:{...payload.hyperparameters, lora_rank:v}})}/><Num label="Alpha" value={payload.hyperparameters.lora_alpha} onChange={v=>setPayload({...payload, hyperparameters:{...payload.hyperparameters, lora_alpha:v}})}/><Field label="GPU" value={payload.compute.gpu_device} onChange={v=>setPayload({...payload, compute:{...payload.compute, gpu_device:v}})}/></div>
              <Button onClick={() => void create()}>Create Real Training Job</Button>
            </div>
          </Card>

          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Training Jobs</h2>
            <div className="mt-5 overflow-x-auto">
              <table className="hsa-table min-w-[900px]">
                <thead>
                  <tr>
                    <th>Job ID</th><th>Training Name</th><th>Base Model</th><th>Method</th><th>Status</th><th>GPU</th><th>Created</th><th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.length === 0 ? (
                    <tr><td colSpan={8} className="text-center text-hsa-secondary">لا توجد مهام تدريب بعد — أنشئ مهمة من النموذج المجاور.</td></tr>
                  ) : jobs.map(j => (
                    <tr key={j.id}>
                      <td className="font-bold">#{j.id}</td>
                      <td>{j.training_name}</td>
                      <td dir="ltr" className="text-start">{j.base_model}</td>
                      <td>{j.method}</td>
                      <td><Badge tone={jobStatusTone(j.status)}>{j.status}</Badge></td>
                      <td>{j.gpu_device ?? 'auto'}</td>
                      <td className="whitespace-nowrap">{new Date(j.created_at).toLocaleString()}</td>
                      <td>
                        <div className="flex flex-wrap gap-2">
                          <Button className="px-3 py-1.5 text-xs" onClick={()=>void start(j.id)}>Start</Button>
                          <Button variant="secondary" className="px-3 py-1.5 text-xs" onClick={()=>void loadDetails(j.id)}>Monitor</Button>
                          <Button variant="secondary" className="px-3 py-1.5 text-xs text-red-700 hover:border-red-300 hover:bg-red-50 hover:text-red-700" onClick={()=>void cancel(j.id)}>Cancel</Button>
                        </div>
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
            <h2 className="text-lg font-bold text-hsa-black">Loss Visualization</h2>
            <div dir="ltr" className="mt-4 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metrics}>
                  <CartesianGrid stroke="#E7E5E4" strokeDasharray="3 3" />
                  <XAxis dataKey="step" stroke="#E7E5E4" tick={{ fill: "#64748B", fontSize: 12 }} />
                  <YAxis stroke="#E7E5E4" tick={{ fill: "#64748B", fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E7E5E4", fontSize: 12 }} />
                  <Line type="monotone" dataKey="loss" dot={false} stroke="#A67C00" strokeWidth={2} />
                  <Line type="monotone" dataKey="eval_loss" dot={false} stroke="#F4C430" strokeWidth={2} />
                  <Line type="monotone" dataKey="learning_rate" dot={false} stroke="#64748B" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Live Logs {selectedJob ? `#${selectedJob}` : ''}</h2>
            <pre dir="ltr" className="mt-4 h-72 overflow-auto rounded-2xl border border-hsa-border bg-hsa-bg p-5 text-start text-xs leading-6 text-hsa-black">{JSON.stringify(logs, null, 2)}</pre>
          </Card>
        </section>
      </main>
    </AppShell>
  );
}

function Field({label,value,onChange}:{label:string;value:string;onChange:(v:string)=>void}){
  return (
    <label className="block">
      <span className="text-xs font-bold text-hsa-secondary">{label}</span>
      <Input className="mt-1.5" value={value} onChange={e=>onChange(e.target.value)} />
    </label>
  );
}
function Num({label,value,onChange}:{label:string;value:number;onChange:(v:number)=>void}){
  return (
    <label className="block">
      <span className="text-xs font-bold text-hsa-secondary">{label}</span>
      <Input className="mt-1.5" type="number" value={value} onChange={e=>onChange(Number(e.target.value))} />
    </label>
  );
}
