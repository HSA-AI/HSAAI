"use client";
import { AppShell } from "@/components/layout/app-shell"; import { Card } from "@/components/ui/card"; import { Button } from "@/components/ui/button"; import { useWorkspaceStore } from "@/store/workspace.store";
const spaces=['default','hr','finance','executive'];
export default function WorkspacePage(){ const {workspaceId,setWorkspace}=useWorkspaceStore(); return <AppShell><div className="space-y-6"><h1 className="text-3xl font-bold">مساحات العمل</h1><div className="grid gap-4 md:grid-cols-4">{spaces.map(s=><Card key={s}><h2 className="text-xl font-semibold">{s}</h2><p className="my-3 text-sm text-slate-500">عزل الذاكرة والملفات والصلاحيات.</p><Button onClick={()=>setWorkspace(s)}>{workspaceId===s?'مفعلة':'تفعيل'}</Button></Card>)}</div></div></AppShell> }
