"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Bot,
  Building2,
  Database,
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
import { useAuth } from "@/lib/auth-provider";

type MessageRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: MessageRole;
  text: string;
  agent?: string;
  createdAt: string;
};

type Conversation = {
  id: string;
  title: string;
  workspaceId: string;
  updatedAt: string;
  messages: ChatMessage[];
};

type ChatApiResponse = {
  answer?: string;
  response?: string;
  text?: string;
  message?: string;
  sources?: Array<{
    title?: string;
    filename?: string;
    score?: number;
  }>;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

const STORAGE_KEY = "hsaai_chat_conversations";

function uid(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 10)}`;
}

function createInitialMessage(): ChatMessage {
  return {
    id: uid("msg"),
    role: "assistant",
    text:
      "مرحباً، أنا HSAAI — مساعد داخلي خاص بمجموعة هائل سعيد أنعم. اسألني عن الوثائق، السياسات، التقارير، الموارد البشرية، المالية، أو مؤشرات الإدارة. عند وجود مصادر مرفوعة سأذكرها بوضوح.",
    agent: "supervisor",
    createdAt: new Date().toISOString(),
  };
}

function makeConversation(workspaceId: string): Conversation {
  return {
    id: uid("conversation"),
    title: "محادثة جديدة",
    workspaceId,
    updatedAt: new Date().toISOString(),
    messages: [createInitialMessage()],
  };
}

function loadConversations(): Conversation[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);

    if (!raw) {
      return [];
    }

    const parsed: unknown = JSON.parse(raw);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter((item): item is Conversation => {
      if (!item || typeof item !== "object") {
        return false;
      }

      const value = item as Partial<Conversation>;

      return (
        typeof value.id === "string" &&
        typeof value.title === "string" &&
        typeof value.workspaceId === "string" &&
        typeof value.updatedAt === "string" &&
        Array.isArray(value.messages)
      );
    });
  } catch {
    return [];
  }
}

function saveConversations(conversations: Conversation[]): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(conversations),
    );
  } catch {
    // Storage failure must not break the chat UI.
  }
}

function getConversationTitle(text: string): string {
  const normalized = text.trim().replace(/\s+/g, " ");

  if (!normalized) {
    return "محادثة جديدة";
  }

  return normalized.length > 42
    ? `${normalized.slice(0, 42)}…`
    : normalized;
}

async function sendChatRequest(
  message: string,
  conversation: Conversation,
  userId: string,
  tenantId: string,
): Promise<ChatApiResponse> {
  const response = await fetch(`${API_BASE}/v1/chat`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      conversation_id: conversation.id,
      workspace_id: conversation.workspaceId,
      user_id: userId,
      tenant_id: tenantId,
    }),
  });

  const contentType = response.headers.get("content-type") || "";

  let payload: ChatApiResponse = {};

  if (contentType.includes("application/json")) {
    payload = (await response.json()) as ChatApiResponse;
  } else {
    const text = await response.text();

    if (text) {
      payload = { text };
    }
  }

  if (!response.ok) {
    throw new Error(
      payload.message ||
        payload.response ||
        "تعذر الاتصال بخدمة HSAAI.",
    );
  }

  return payload;
}

export default function ChatPage() {
  const { workspaceId, setWorkspace } = useWorkspaceStore();
  const { user } = useAuth();

  const userId =
    user?.sub ||
    user?.preferred_username ||
    user?.username ||
    "anonymous";

  const tenantId = user?.tenant_id || "hsa-group";

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  const newChat = useCallback(
    (targetWorkspace = workspaceId || "default") => {
      const conversation = makeConversation(targetWorkspace);

      setConversations((previous) => [
        conversation,
        ...previous,
      ]);

      setActiveId(conversation.id);
      setWorkspace(targetWorkspace);
      setInput("");
      setError("");
      setSidebarOpen(false);
    },
    [setWorkspace, workspaceId],
  );

  useEffect(() => {
    const shouldOpenNewChat =
      typeof window !== "undefined" &&
      (window.localStorage.getItem("hsaai_open_new_chat") === "1" ||
        new URLSearchParams(window.location.search).get("new") === "1");

    if (typeof window !== "undefined") {
      window.localStorage.removeItem("hsaai_open_new_chat");

      if (
        new URLSearchParams(window.location.search).get("new") ===
        "1"
      ) {
        window.history.replaceState(null, "", "/chat");
      }
    }

    const loaded = loadConversations();

    if (shouldOpenNewChat) {
      const first = makeConversation(
        workspaceId || "default",
      );

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
      return;
    }

    const first = makeConversation(
      workspaceId || "default",
    );

    setConversations([first]);
    setActiveId(first.id);
    setWorkspace(first.workspaceId);
  }, [setWorkspace, workspaceId]);

  useEffect(() => {
    if (conversations.length > 0) {
      saveConversations(conversations);
    }
  }, [conversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [activeId, conversations, loading]);

  useEffect(() => {
    function handleAssistantNewChat() {
      newChat(workspaceId || "default");
    }

    window.addEventListener(
      "hsaai:new-chat",
      handleAssistantNewChat,
    );

    return () => {
      window.removeEventListener(
        "hsaai:new-chat",
        handleAssistantNewChat,
      );
    };
  }, [newChat, workspaceId]);

  useEffect(() => {
    document.body.style.overflow = sidebarOpen
      ? "hidden"
      : "";

    return () => {
      document.body.style.overflow = "";
    };
  }, [sidebarOpen]);

  const active = useMemo(
    () =>
      conversations.find(
        (conversation) =>
          conversation.id === activeId,
      ),
    [conversations, activeId],
  );

  const updateActive = useCallback(
    (
      mutator: (
        conversation: Conversation,
      ) => Conversation,
    ) => {
      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.id === activeId
            ? mutator(conversation)
            : conversation,
        ),
      );
    },
    [activeId],
  );

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const message = input.trim();

    if (!message || loading || !active) {
      return;
    }

    setInput("");
    setError("");
    setLoading(true);

    const userMessage: ChatMessage = {
      id: uid("msg"),
      role: "user",
      text: message,
      createdAt: new Date().toISOString(),
    };

    const updatedConversation: Conversation = {
      ...active,
      title:
        active.messages.length <= 1
          ? getConversationTitle(message)
          : active.title,
      updatedAt: new Date().toISOString(),
      messages: [
        ...active.messages,
        userMessage,
      ],
    };

    setConversations((previous) =>
      previous.map((conversation) =>
        conversation.id === active.id
          ? updatedConversation
          : conversation,
      ),
    );

    try {
      const result = await sendChatRequest(
        message,
        updatedConversation,
        userId,
        tenantId,
      );

      const answer =
        result.answer ||
        result.response ||
        result.text ||
        result.message ||
        "تم استلام الطلب، ولكن لم تُرجع الخدمة نصاً.";

      const assistantMessage: ChatMessage = {
        id: uid("msg"),
        role: "assistant",
        text: answer,
        agent: "supervisor",
        createdAt: new Date().toISOString(),
      };

      updateActive((conversation) => ({
        ...conversation,
        updatedAt: new Date().toISOString(),
        messages: [
          ...conversation.messages,
          assistantMessage,
        ],
      }));
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "حدث خطأ غير متوقع أثناء الاتصال بخدمة HSAAI.";

      setError(message);

      const assistantMessage: ChatMessage = {
        id: uid("msg"),
        role: "assistant",
        text:
          "تعذر تنفيذ الطلب حالياً. يرجى التحقق من خدمة API وتسجيل الدخول ثم المحاولة مرة أخرى.",
        agent: "system",
        createdAt: new Date().toISOString(),
      };

      updateActive((conversation) => ({
        ...conversation,
        updatedAt: new Date().toISOString(),
        messages: [
          ...conversation.messages,
          assistantMessage,
        ],
      }));
    } finally {
      setLoading(false);
    }
  }

  function selectConversation(
    conversation: Conversation,
  ) {
    setActiveId(conversation.id);
    setWorkspace(
      conversation.workspaceId || "default",
    );
    setError("");
    setSidebarOpen(false);
  }

  function deleteConversation(id: string) {
    setConversations((previous) => {
      const remaining = previous.filter(
        (conversation) =>
          conversation.id !== id,
      );

      if (remaining.length === 0) {
        const replacement = makeConversation(
          workspaceId || "default",
        );

        setActiveId(replacement.id);
        setWorkspace(replacement.workspaceId);

        return [replacement];
      }

      if (id === activeId) {
        setActiveId(remaining[0].id);
        setWorkspace(
          remaining[0].workspaceId || "default",
        );
      }

      return remaining;
    });
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="flex min-h-screen">
        {sidebarOpen && (
          <button
            type="button"
            aria-label="إغلاق القائمة"
            className="fixed inset-0 z-30 bg-black/60 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        <aside
          className={[
            "fixed inset-y-0 right-0 z-40 flex w-80 flex-col border-l border-slate-800 bg-slate-950 transition-transform lg:static lg:translate-x-0",
            sidebarOpen
              ? "translate-x-0"
              : "translate-x-full",
          ].join(" ")}
        >
          <div className="flex items-center justify-between border-b border-slate-800 p-4">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-slate-900 p-2">
                <Bot className="h-5 w-5 text-hsa-yellow" />
              </div>

              <div>
                <h2 className="font-bold">
                  محادثات HSAAI
                </h2>
                <p className="text-xs text-slate-500">
                  المساعد المؤسسي
                </p>
              </div>
            </div>

            <button
              type="button"
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-900 hover:text-white lg:hidden"
              onClick={() =>
                setSidebarOpen(false)
              }
              aria-label="إغلاق"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="p-4">
            <button
              type="button"
              onClick={() =>
                newChat(workspaceId || "default")
              }
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-hsa-yellow px-4 py-3 font-bold text-slate-950 transition hover:opacity-90"
            >
              <Plus className="h-5 w-5" />
              محادثة جديدة
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-3 pb-4">
            <div className="space-y-2">
              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() =>
                    selectConversation(conversation)
                  }
                  className={[
                    "group w-full rounded-xl border p-3 text-right transition",
                    conversation.id === activeId
                      ? "border-hsa-yellow/40 bg-slate-900"
                      : "border-transparent hover:border-slate-800 hover:bg-slate-900/70",
                  ].join(" ")}
                >
                  <div className="flex items-start gap-3">
                    <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />

                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">
                        {conversation.title}
                      </p>

                      <p className="mt-1 text-xs text-slate-500">
                        {conversation.messages.length} رسالة
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="border-t border-slate-800 p-4">
            <div className="flex items-center gap-3 rounded-xl bg-slate-900 p-3">
              <div className="rounded-full bg-slate-800 p-2">
                <UserRound className="h-4 w-4" />
              </div>

              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">
                  {user?.preferred_username ||
                    user?.username ||
                    "مستخدم HSAAI"}
                </p>

                <p className="truncate text-xs text-slate-500">
                  {tenantId}
                </p>
              </div>
            </div>
          </div>
        </aside>

        <section className="flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/95 backdrop-blur">
            <div className="flex h-16 items-center justify-between px-4 lg:px-8">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setSidebarOpen(true)
                  }
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-900 hover:text-white lg:hidden"
                  aria-label="فتح المحادثات"
                >
                  <Menu className="h-5 w-5" />
                </button>

                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-hsa-yellow/10 p-2">
                    <Sparkles className="h-5 w-5 text-hsa-yellow" />
                  </div>

                  <div>
                    <h1 className="font-bold">
                      HSAAI
                    </h1>
                    <p className="text-xs text-slate-500">
                      Enterprise AI Assistant
                    </p>
                  </div>
                </div>
              </div>

              <div className="hidden items-center gap-3 sm:flex">
                <div className="flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400">
                  <ShieldCheck className="h-4 w-4" />
                  جلسة آمنة
                </div>

                <div className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-400">
                  {workspaceId || "default"}
                </div>
              </div>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto flex w-full max-w-5xl flex-col px-4 py-6 lg:px-8">
              {!active ? (
                <div className="flex min-h-[60vh] items-center justify-center">
                  <div className="text-center">
                    <Bot className="mx-auto mb-4 h-12 w-12 text-slate-600" />
                    <p className="text-slate-400">
                      لا توجد محادثة نشطة.
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div className="mb-6 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                      <Database className="mb-3 h-5 w-5 text-hsa-yellow" />
                      <p className="text-sm font-bold">
                        معرفة مؤسسية
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        RAG ومصادر داخلية
                      </p>
                    </div>

                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                      <Building2 className="mb-3 h-5 w-5 text-hsa-yellow" />
                      <p className="text-sm font-bold">
                        مساحة العمل
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {workspaceId || "default"}
                      </p>
                    </div>

                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                      <Search className="mb-3 h-5 w-5 text-hsa-yellow" />
                      <p className="text-sm font-bold">
                        بحث ذكي
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        بحث دلالي في المعرفة
                      </p>
                    </div>
                  </div>

                  <div className="space-y-5">
                    {active.messages.map((message) => (
                      <div
                        key={message.id}
                        className={[
                          "flex gap-3",
                          message.role === "user"
                            ? "justify-end"
                            : "justify-start",
                        ].join(" ")}
                      >
                        {message.role ===
                          "assistant" && (
                          <div className="mt-1 shrink-0 rounded-xl bg-hsa-yellow/10 p-2">
                            <Bot className="h-5 w-5 text-hsa-yellow" />
                          </div>
                        )}

                        <div
                          className={[
                            "max-w-[85%] rounded-2xl px-4 py-3 leading-7",
                            message.role === "user"
                              ? "bg-hsa-yellow font-medium text-slate-950"
                              : "border border-slate-800 bg-slate-900 text-slate-200",
                          ].join(" ")}
                        >
                          <p className="whitespace-pre-wrap">
                            {message.text}
                          </p>

                          {message.agent && (
                            <p className="mt-2 text-[11px] opacity-50">
                              agent: {message.agent}
                            </p>
                          )}
                        </div>

                        {message.role ===
                          "user" && (
                          <div className="mt-1 shrink-0 rounded-xl bg-slate-800 p-2">
                            <UserRound className="h-5 w-5 text-slate-300" />
                          </div>
                        )}
                      </div>
                    ))}

                    {loading && (
                      <div className="flex items-center gap-3">
                        <div className="rounded-xl bg-hsa-yellow/10 p-2">
                          <Bot className="h-5 w-5 text-hsa-yellow" />
                        </div>

                        <div className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3">
                          <div className="flex items-center gap-2 text-sm text-slate-400">
                            <span className="h-2 w-2 animate-pulse rounded-full bg-slate-500" />
                            <span className="h-2 w-2 animate-pulse rounded-full bg-slate-500 [animation-delay:150ms]" />
                            <span className="h-2 w-2 animate-pulse rounded-full bg-slate-500 [animation-delay:300ms]" />
                            <span className="mr-2">
                              HSAAI يفكر...
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    <div ref={bottomRef} />
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="border-t border-slate-800 bg-slate-950 p-4 lg:p-6">
            <div className="mx-auto max-w-5xl">
              {error && (
                <div
                  role="alert"
                  className="mb-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300"
                >
                  {error}
                </div>
              )}

              <form
                onSubmit={handleSubmit}
                className="relative"
              >
                <input
                  value={input}
                  onChange={(event) =>
                    setInput(event.target.value)
                  }
                  disabled={loading || !active}
                  placeholder="اكتب سؤالك إلى HSAAI..."
                  aria-label="رسالة المحادثة"
                  className="min-h-14 w-full rounded-2xl border border-slate-700 bg-slate-900 px-5 pl-14 text-right text-white outline-none transition placeholder:text-slate-500 focus:border-hsa-yellow/50 focus:ring-2 focus:ring-hsa-yellow/10 disabled:cursor-not-allowed disabled:opacity-50"
                />

                <button
                  type="submit"
                  disabled={
                    loading ||
                    !input.trim() ||
                    !active
                  }
                  aria-label="إرسال الرسالة"
                  className="absolute left-2 top-2 flex h-10 w-10 items-center justify-center rounded-xl bg-hsa-yellow text-slate-950 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <SendHorizontal className="h-5 w-5" />
                </button>
              </form>

              <p className="mt-2 text-center text-[11px] text-slate-600">
                HSAAI يستخدم مصادر المعرفة المؤسسية المتاحة
                وفق صلاحيات حسابك.
              </p>
            </div>
          </div>
        </section>
      </div>

      {active && conversations.length > 1 && (
        <div className="fixed bottom-24 left-4 z-10 hidden lg:block">
          <button
            type="button"
            onClick={() =>
              deleteConversation(active.id)
            }
            className="text-xs text-slate-600 transition hover:text-red-400"
          >
            حذف المحادثة الحالية
          </button>
        </div>
      )}
    </main>
  );
}
