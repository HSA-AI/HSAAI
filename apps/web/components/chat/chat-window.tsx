"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { sendChat } from "@/services/chat.service";
import { useWorkspaceStore } from "@/store/workspace.store";
type Msg={role:"user"|"assistant",content:string,agent?:string};
export function ChatWindow(){ const [input,setInput]=useState(""); const [messages,setMessages]=useState<Msg[]>([{role:"assistant",content:"مرحباً، أنا HSAAI Enterprise. اختر مساحة العمل وابدأ المحادثة."}]); const [loading,setLoading]=useState(false); const workspaceId=useWorkspaceStore(s=>s.workspaceId);
async function submit(){ if(!input.trim()) return; const text=input; setInput(""); setMessages(m=>[...m,{role:"user",content:text}]); setLoading(true); try{ const res=await sendChat({user:"admin",message:text,workspace_id:workspaceId}); setMessages(m=>[...m,{role:"assistant",content:res.response,agent:res.agent}]); } finally { setLoading(false); } }
return <Card className="flex h-[calc(100vh-8rem)] flex-col"><div className="flex-1 space-y-4 overflow-auto p-2">{messages.map((m,i)=><div key={i} className={m.role==='user'?"text-left":"text-right"}><div className="inline-block max-w-3xl rounded-2xl border px-4 py-3 dark:border-slate-800"><p className="whitespace-pre-wrap">{m.content}</p>{m.agent&&<span className="mt-2 block text-xs text-slate-500">Agent: {m.agent}</span>}</div></div>)}{loading&&<p className="text-sm text-slate-500">HSAAI يكتب...</p>}</div><div className="flex gap-3 border-t pt-4 dark:border-slate-800"><Textarea value={input} onChange={e=>setInput(e.target.value)} placeholder="اكتب طلبك هنا..." onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit()}}}/><Button onClick={submit} disabled={loading}>إرسال</Button></div></Card> }
