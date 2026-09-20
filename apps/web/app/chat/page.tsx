"use client";
import Image from "next/image";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Building2,
  Check,
  Copy,
  FileText,
  Menu,
  Plus,
  Search,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useAuth } from "@/lib/auth-provider";  // FIX v2.1 (P0): wire real user identity
import { brand } from "@/lib/brand";

const API = process.env.NEXT_PUBLIC_API_URL || "";

type Role = "user" | "assistant";
type Source = { filename?: string; chunk_index?: number; score?: number; doc_id?: string };
type Message = { id: string; role: Role; text: string; agent?: string; sources?: Source[]; createdAt: string };
type Conversation = { id: string; title: string; workspaceId: string; messages: Message[]; updatedAt: string };

const STORAGE_KEY = "hsaai_chatgpt_like_conversations_v1";

const starters = [
  "لخص لي آخر سياسة مرفوعة في قاعدة المعرفة",
  "اكتب تقريراً تنفيذياً مختصراً للإدارة العليا",
  "حلل فاتورة أو ميزانية حسب وثائق المؤسسة",
  "ما الخطوات الآمنة لربط النظام بأنظمة HR و ERP؟",
];

const workspaces = [
  { id: "default", label: "عام", hint: "محادثة عامة" },
  { id: "hr", label: "HR", hint: "الموظفون والسياسات" },
  { id: "finance", label: "Finance", hint: "الفواتير والتقارير" },
  { id: "executive", label: "Executive", hint: "ملخصات وقرارات" },
  { id: "knowledge", label: "Knowledge", hint: "وثائق ومصادر" },
  { id: "it", label: "IT", hint: "الدعم والتشغيل" },
];

function uid(prefix = "id") {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

// SECURITY FIX v2.0: Removed authHeaders() that read token from localStorage (XSS leak risk).
// All fetch calls now use `credentials: "include"` to send httpOnly cookies automatically.
function authHeaders(): Record<string, string> {
  // Return only non-auth headers — auth is via httpOnly cookie
  return { "X-Requested-With": "XMLHttpRequest" };
}

function loadConversations(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]") as Conversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveConversations(items: Conversation[]) {
  if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

function makeConversation(workspaceId: string): Conversation {
  return {
    id: uid("conv"),
    title: "محادثة جديدة",
    workspaceId,
    updatedAt: new Date().toISOString(),
    messages: [
      {
        id: uid("msg"),
        role: "assistant",
        text: "مرحباً، أنا HSAAI — مساعد داخلي خاص بمجموعة هائل سعيد أنعم. اسألني عن الوثائق، السياسات، التقارير، الموارد البشرية، المالية، أو مؤشرات الإدارة. عند وجود مصادر مرفوعة سأذكرها بوضوح.",
        agent: "supervisor",
        createdAt: new Date().toISOString(),
      },
    ],
  };
}

/** Presentational helper — HH:MM timestamp under each bubble */
function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("ar", { hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
  } catch {
    return "";
  }
}

export default function ChatPage() {
  const { workspaceId, setWorkspace } = useWorkspaceStore();
  // FIX v2.1 (P0): use real authenticated user identity instead of hardcoded "current-user".
  const { user } = useAuth();
  const userId = user?.sub || user?.preferred_username || "anonymous";
  const tenantId = user?.tenant_id || "hsa-group";
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const shouldOpenNewChat =
      typeof window !== "undefined" &&
      (window.localStorage.getItem("hsaai_open_new_chat") === "1" ||
        new URLSearchParams(window.location.search).get("new") === "1");

    if (typeof window !== "undefined") {
      window.localStorage.removeItem("hsaai_open_new_chat");
      if (new URLSearchParams(window.location.search).get("new") === "1") {
        window.history.replaceState(null, "", "/chat");
      }
    }

    const loaded = loadConversations();
    if (shouldOpenNewChat) {
      const first = makeConversation(workspaceId || "default");
      const next = [first, ...loaded];
      setConversations(next);
      setActiveId(first.id);
      setWorkspace(first.workspaceId);
      saveConversations(next);
      return;
    }

    if (loaded.length > 0) {
      setConversations(loaded);
      setActiveId(loaded[0].id);
      setWorkspace(loaded[0].workspaceId || "default");
    } else {
      const first = makeConversation(workspaceId || "default");
      setConversations([first]);
      setActiveId(first.id);
      saveConversations([first]);
    }
  // Hydrate persisted conversations once; workspace changes should not reset the chat.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    saveConversations(conversations);
  }, [conversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeId, conversations, loading]);

  useEffect(() => {
    function handleAssistantNewChat() {
      newChat(workspaceId || "default");
    }

    window.addEventListener("hsaai:new-chat", handleAssistantNewChat);
    return () => window.removeEventListener("hsaai:new-chat", handleAssistantNewChat);
  // The event handler uses the current workspace and state setters only.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  useEffect(() => {
    document.body.style.overflow = sidebarOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [sidebarOpen]);

  const active = useMemo(() => conversations.find((c) => c.id === activeId), [conversations, activeId]);

  function newChat(targetWorkspace = workspaceId || "default") {
    const c = makeConversation(targetWorkspace);
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
    setWorkspace(targetWorkspace);
    setInput("");
    setError("");
    setSidebarOpen(false);
  }

  function updateActive(mutator: (conversation: Conversation) => Conversation) {
    setConversations((prev) => prev.map((c) => (c.id === activeId ? mutator(c) : c)));
  }

  /** Presentational action — copy assistant answer (design system: message actions) */
  async function copyMessage(message: Message) {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopiedId(message.id);
      window.setTimeout(() => setCopiedId(""), 1600);
    } catch {
      // Clipboard unavailable (permissions/insecure context) — silently ignore.
    }
  }

  async function submit(e?: FormEvent<HTMLFormElement>, forcedText?: string) {
    e?.preventDefault();
    const text = (forcedText || input).trim();
    if (!text || !active || loading) return;

    const userMsg: Message = { id: uid("msg"), role: "user", text, createdAt: new Date().toISOString() };
    updateActive((c) => ({
      ...c,
      title: c.title === "محادثة جديدة" ? text.slice(0, 42) : c.title,
      workspaceId,
      updatedAt: new Date().toISOString(),
      messages: [...c.messages, userMsg],
    }));
    setInput("");
    setLoading(true);
    setError("");

    try {
      // FIX v2.1 (P0): Real streaming SSE via fetch + ReadableStream.
      // Previously this used non-streaming fetch().json() — users saw a static
      // spinner for the full LLM duration with no token-by-token rendering.
      // Now we stream tokens as they arrive from the backend.
      const assistantMsgId = uid("msg");
      // Add an empty assistant message that we'll fill as tokens stream in.
      updateActive((c) => ({
        ...c,
        updatedAt: new Date().toISOString(),
        messages: [
          ...c.messages,
          { id: assistantMsgId, role: "assistant", text: "", agent: "supervisor", sources: [], createdAt: new Date().toISOString() },
        ],
      }));

      const response = await fetch(`${API}/v1/chat`, {
        method: "POST",
        credentials: "include", // SECURITY v2.0: Send httpOnly cookie
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
          "X-Workspace-ID": workspaceId,
          ...authHeaders(),
        },
        body: JSON.stringify({
          user: userId,  // FIX v2.1 (P0): real authenticated user from useAuth()
          message: text,
          workspace_id: workspaceId,
          tenant_id: tenantId,  // FIX v2.1 (P0): real tenant from JWT claims
          conversation_id: active.id,
          stream: true,  // Request streaming from backend
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Request failed: ${response.status}`);
      }

      // If the backend returns SSE (Content-Type: text/event-stream), stream tokens.
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("text/event-stream") && response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let fullText = "";
        let agent = "supervisor";
        const sources: Source[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          // SSE events are separated by double newlines
          const events = buffer.split("\n\n");
          buffer = events.pop() || "";  // last partial event stays in buffer
          for (const evt of events) {
            for (const line of evt.split("\n")) {
              if (!line.startsWith("data:")) continue;
              const payload = line.slice(5).trim();
              if (!payload || payload === "[DONE]") continue;
              try {
                const chunk = JSON.parse(payload);
                if (chunk.token) {
                  fullText += chunk.token;
                  // Update the assistant message text in place.
                  updateActive((c) => ({
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === assistantMsgId ? { ...m, text: fullText } : m
                    ),
                  }));
                }
                if (chunk.agent) agent = chunk.agent;
                if (chunk.sources) sources.push(...chunk.sources);
              } catch {
                // Non-JSON data line — treat as plain text token
                fullText += payload;
                updateActive((c) => ({
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === assistantMsgId ? { ...m, text: fullText } : m
                  ),
                }));
              }
            }
          }
        }
        // Final update with agent + sources
        updateActive((c) => ({
          ...c,
          updatedAt: new Date().toISOString(),
          messages: c.messages.map((m) =>
            m.id === assistantMsgId ? { ...m, text: fullText || "لم يرجع النظام إجابة.", agent, sources } : m
          ),
        }));
      } else {
        // Fallback: backend returned plain JSON (no streaming) — handle legacy way.
        const data = await response.json();
        updateActive((c) => ({
          ...c,
          updatedAt: new Date().toISOString(),
          messages: c.messages.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  text: data.response || data.text || "لم يرجع النظام إجابة.",
                  agent: data.agent || data.orchestration?.agent || "supervisor",
                  sources: data.sources || [],
                }
              : m
          ),
        }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر الاتصال بمنصة HSAAI.");
    } finally {
      setLoading(false);
    }
  }

  const sidebar = (
    <div className="flex h-full flex-col bg-white p-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
      <div className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-hsa-border bg-hsa-bg p-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold"><Building2 size={20} /></span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-hsa-black">HSAAI</p>
            <p className="truncate text-xs text-hsa-secondary">Private ChatGPT for HSA Group</p>
          </div>
        </div>
        <button onClick={() => setSidebarOpen(false)} className="rounded-lg border border-hsa-border bg-white p-2 text-hsa-secondary hover:bg-hsa-soft lg:hidden" aria-label="إغلاق القائمة">
          <X size={18} />
        </button>
      </div>

      <button onClick={() => newChat()} className="mb-4 flex min-h-12 items-center justify-center gap-2 rounded-xl bg-hsa-yellow px-4 py-3 text-sm font-semibold text-hsa-black transition hover:bg-hsa-gold-dark hover:text-white active:scale-[.98]">
        <Plus size={18} /> محادثة جديدة
      </button>

      <div className="mb-3 flex items-center gap-2 rounded-xl border border-hsa-border bg-hsa-bg px-3 py-2 text-hsa-secondary">
        <Search size={16} /> <span className="text-xs">سجل المحادثات المحلي</span>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain pe-1">
        {conversations.map((c) => {
          const isActive = c.id === activeId;
          return (
            <button
              key={c.id}
              onClick={() => {
                setActiveId(c.id);
                setWorkspace(c.workspaceId || "default");
                setSidebarOpen(false);
              }}
              className={`w-full rounded-xl border px-3 py-3 text-start text-sm transition active:scale-[.99] ${
                isActive
                  ? "border-hsa-yellow/50 bg-hsa-soft text-hsa-gold"
                  : "border-hsa-border bg-white text-hsa-black hover:border-hsa-gold/40 hover:bg-hsa-soft/60"
              }`}
            >
              <span className="line-clamp-1 font-bold">{c.title}</span>
              <span className="mt-1 block text-xs text-hsa-secondary">{c.workspaceId} · {c.messages.length} رسائل</span>
            </button>
          );
        })}
      </div>

      <div className="mt-4 rounded-xl border border-hsa-border bg-hsa-bg p-3 text-xs text-hsa-secondary">
        <div className="mb-1 flex items-center gap-2 font-bold text-hsa-black"><ShieldCheck size={16} className="text-hsa-gold" /> وضع مؤسسي خاص</div>
        <p>Local LLM + RAG + RBAC + Audit + Tenant Isolation</p>
      </div>
    </div>
  );

  return (
    <main className="flex h-dvh overflow-hidden bg-hsa-bg text-hsa-black">
      {sidebarOpen && <button className="fixed inset-0 z-40 bg-black/45 backdrop-blur-sm lg:hidden" onClick={() => setSidebarOpen(false)} aria-label="إغلاق القائمة الجانبية" />}

      <aside className="hidden w-80 shrink-0 overflow-hidden border-e border-hsa-border bg-white lg:block">
        {sidebar}
      </aside>

      <aside className={`fixed inset-y-0 start-0 z-50 w-[min(86vw,22rem)] overflow-hidden border-e border-hsa-border bg-white shadow-hsa-card-hover transition-transform duration-300 lg:hidden ${sidebarOpen ? "translate-x-0" : "ltr:-translate-x-full rtl:translate-x-full"}`}>
        {sidebar}
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between border-b border-hsa-border bg-white/90 px-3 py-3 backdrop-blur supports-[height:100dvh]:pt-[max(.75rem,env(safe-area-inset-top))] sm:px-4 lg:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button onClick={() => setSidebarOpen((v) => !v)} className="flex min-h-11 min-w-11 items-center justify-center rounded-xl border border-hsa-border bg-white p-2 text-hsa-black hover:bg-hsa-soft active:scale-95" aria-label="فتح القائمة الجانبية"><Menu size={20} /></button>
            <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="hidden h-10 w-10 rounded-full object-cover sm:block" />
            <div className="min-w-0">
              <h1 className="truncate text-base font-bold text-hsa-black sm:text-lg">HSAAI Chat</h1>
              <p className="line-clamp-1 text-micro text-hsa-secondary sm:text-xs">مساعد مؤسسي ذكي مخصص لأنظمة مجموعة هائل سعيد أنعم</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 md:flex">
            {workspaces.map((w) => (
              <button
                key={w.id}
                onClick={() => { setWorkspace(w.id); if (active) updateActive((c) => ({ ...c, workspaceId: w.id })); }}
                title={w.hint}
                className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                  workspaceId === w.id
                    ? "bg-hsa-yellow text-hsa-black"
                    : "border border-hsa-border bg-white text-hsa-secondary hover:border-hsa-gold/40 hover:text-hsa-black"
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto overscroll-contain px-3 py-4 sm:px-4 sm:py-6 lg:px-8">
          <div className="mx-auto max-w-4xl space-y-4 sm:space-y-5">
            <div className="flex gap-2 overflow-x-auto pb-1 md:hidden">
              {workspaces.map((w) => (
                <button
                  key={w.id}
                  onClick={() => { setWorkspace(w.id); if (active) updateActive((c) => ({ ...c, workspaceId: w.id })); }}
                  title={w.hint}
                  className={`shrink-0 rounded-full px-3 py-2 text-xs font-semibold transition ${
                    workspaceId === w.id
                      ? "bg-hsa-yellow text-hsa-black"
                      : "border border-hsa-border bg-white text-hsa-secondary"
                  }`}
                >
                  {w.label}
                </button>
              ))}
            </div>

            {active?.messages.map((m) => (
              <article key={m.id} className={`flex gap-2 sm:gap-3 ${m.role === "user" ? "flex-row-reverse justify-start" : "justify-start"}`}>
                {m.role === "assistant" && (
                  <div className="mt-1 hidden h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-hsa-yellow bg-white sm:flex">
                    <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="h-full w-full object-cover" />
                  </div>
                )}
                <div className={`max-w-[92%] break-words rounded-2xl border px-4 py-3 sm:max-w-[85%] sm:px-5 sm:py-4 ${
                  m.role === "user"
                    ? "border-hsa-border bg-white shadow-hsa-card"
                    : "border-hsa-yellow/30 bg-hsa-soft"
                }`}>
                  <p className="whitespace-pre-wrap text-body-lg leading-7 text-hsa-black sm:leading-8">{m.text}</p>

                  {m.role === "assistant" && (
                    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-hsa-yellow/30 pt-2.5 text-micro text-hsa-secondary">
                      <span className="rounded-full border border-hsa-yellow/30 bg-white px-2 py-0.5 font-semibold text-hsa-gold">Agent: {m.agent || "supervisor"}</span>
                      {(m.sources?.length || 0) > 0 && (
                        <span className="rounded-full bg-hsa-yellow/20 px-2 py-0.5 font-semibold text-hsa-gold">{m.sources?.length} مصادر</span>
                      )}
                      <time dateTime={m.createdAt} className="ms-auto">{formatTime(m.createdAt)}</time>
                      {m.text && (
                        <button
                          type="button"
                          onClick={() => void copyMessage(m)}
                          className="inline-flex items-center gap-1 rounded-full border border-hsa-border bg-white px-2 py-0.5 font-semibold text-hsa-secondary transition hover:border-hsa-gold/50 hover:text-hsa-gold"
                          aria-label="نسخ الإجابة"
                        >
                          {copiedId === m.id ? <Check size={12} /> : <Copy size={12} />}
                          {copiedId === m.id ? "تم النسخ" : "نسخ"}
                        </button>
                      )}
                    </div>
                  )}
                  {m.role === "user" && (
                    <div className="mt-2 text-end">
                      <time dateTime={m.createdAt} className="text-micro text-hsa-secondary">{formatTime(m.createdAt)}</time>
                    </div>
                  )}

                  {(m.sources?.length || 0) > 0 && (
                    <div className="mt-3 space-y-1.5 overflow-hidden rounded-xl border border-hsa-border bg-white p-3 text-xs text-hsa-secondary">
                      <p className="font-bold text-hsa-black">المصادر</p>
                      {m.sources?.map((s, i) => (
                        <div key={`${s.filename}-${i}`} className="truncate">
                          <FileText className="me-1 inline text-hsa-gold" size={13} />
                          [{i + 1}] {s.filename || "document"} · chunk {s.chunk_index ?? 0}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {m.role === "user" && (
                  <div className="mt-1 hidden h-9 w-9 shrink-0 items-center justify-center rounded-full border border-hsa-border bg-white text-hsa-secondary sm:flex"><UserRound size={18} /></div>
                )}
              </article>
            ))}

            {active && active.messages.length <= 1 && (
              <div className="grid gap-3 sm:grid-cols-2">
                {starters.map((s) => (
                  <button key={s} onClick={() => void submit(undefined, s)} className="rounded-2xl border border-hsa-border bg-white p-4 text-start text-body-lg leading-7 text-hsa-black shadow-hsa-card transition hover:-translate-y-0.5 hover:border-hsa-gold/50 hover:bg-hsa-soft/60 hover:shadow-hsa-card-hover active:scale-[.99]">
                    <Sparkles className="mb-2 text-hsa-gold" size={18} />{s}
                  </button>
                ))}
              </div>
            )}

            {loading && (
              <div className="flex items-center gap-3 rounded-2xl border border-hsa-yellow/30 bg-hsa-soft px-4 py-3 text-sm text-hsa-black" role="status" aria-live="polite">
                <span className="flex items-center gap-1">
                  <span className="hsa-typing-dot" /><span className="hsa-typing-dot" /><span className="hsa-typing-dot" />
                </span>
                HSAAI يبحث في المعرفة الداخلية ويولّد الإجابة...
              </div>
            )}

            {error && <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm leading-7 text-red-800">{error}</div>}
            <div ref={bottomRef} />
          </div>
        </div>

        <footer className="border-t border-hsa-border bg-white p-3 pb-[calc(.75rem+env(safe-area-inset-bottom))] sm:p-4 lg:p-5">
          <form onSubmit={submit} className="mx-auto flex max-w-4xl items-end gap-2 rounded-2xl border border-hsa-border bg-hsa-bg p-2 shadow-hsa-card sm:gap-3 sm:p-3">
            {/* text-[16px] on mobile is intentional: iOS zooms into inputs with font-size < 16px (WCAG-friendly) */}
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void submit(); } }}
              placeholder="اكتب رسالتك إلى HSAAI..."
              className="max-h-36 min-h-11 flex-1 resize-none bg-transparent px-3 py-3 text-[16px] leading-7 text-hsa-black outline-none placeholder:text-hsa-secondary/70 sm:text-sm"
              rows={1}
              aria-label="نص الرسالة"
            />
            <button type="submit" disabled={loading || !input.trim()} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-hsa-yellow text-hsa-black transition hover:bg-hsa-gold-dark hover:text-white disabled:cursor-not-allowed disabled:opacity-40 sm:h-12 sm:w-12" aria-label="إرسال الرسالة">
              <SendHorizontal size={20} />
            </button>
          </form>
          <p className="mx-auto mt-2 max-w-4xl text-center text-nano text-hsa-secondary sm:text-micro">HSAAI قد يستخدم الوثائق الداخلية المصرح بها فقط. راجع المصادر قبل اتخاذ قرارات رسمية.</p>
        </footer>
      </section>
    </main>
  );
}
