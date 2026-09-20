"use client";
import Image from "next/image";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Minimize2, Send, ShieldCheck, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { sendChat } from "@/services/chat.service";
import { useWorkspaceStore } from "@/store/workspace.store";
import { brand } from "@/lib/brand";

type AssistantMessage = {
  role: "assistant" | "user";
  content: string;
  agent?: string;
};

const quickPrompts = [...brand.assistant.quickPrompts];

export function FloatingAssistant() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const workspaceId = useWorkspaceStore((state) => state.workspaceId);
  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      role: "assistant",
      content:
        "مرحباً، أنا مساعد HSAAI الداخلي. اسألني عن السياسات، المستندات، الأنظمة، أو أي خدمة مؤسسية مصرح لك بها.",
    },
  ]);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, open]);

  function openNewChat() {
    setOpen(false);
    if (pathname === "/chat") {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("hsaai:new-chat"));
      }
      return;
    }

    if (typeof window !== "undefined") {
      window.localStorage.setItem("hsaai_open_new_chat", "1");
    }
    router.push("/chat?new=1");
  }

  async function submit(text?: string) {
    const value = (text ?? input).trim();
    if (!value || loading) return;

    setInput("");
    setOpen(true);
    setMessages((current) => [...current, { role: "user", content: value }]);
    setLoading(true);

    try {
      const response = await sendChat({
        user: "employee",
        message: value,
        workspace_id: workspaceId || "hsa-main-workspace",
      });
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response?.response || "تم استلام طلبك، لكن لم تصل استجابة واضحة من الخدمة.",
          agent: response?.agent,
        },
      ]);
    } catch {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "تعذر الاتصال بخدمة HSAAI حالياً. تأكد من تشغيل API Gateway أو جرّب لاحقاً.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed bottom-[calc(1rem+env(safe-area-inset-bottom))] start-4 z-[80] print:hidden sm:bottom-6 sm:start-6" aria-live="polite">
      {open && (
        <section
          className={[
            "relative mb-4 overflow-hidden rounded-2xl border border-hsa-border bg-white shadow-hsa-card-hover",
            expanded ? "h-[min(78dvh,720px)] w-[min(94vw,680px)]" : "h-[min(72dvh,560px)] w-[min(94vw,420px)]",
          ].join(" ")}
          role="dialog"
          aria-label="مساعد HSAAI السريع"
        >
          <span aria-hidden className="absolute inset-x-0 top-0 z-10 h-1 bg-hsa-yellow" />

          <header className="flex items-center justify-between border-b border-hsa-border bg-white px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border-2 border-hsa-yellow bg-hsa-soft">
                <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt={brand.assistant.name} className="h-full w-full object-cover" />
              </div>
              <div>
                <p className="text-sm font-semibold text-hsa-black">{brand.assistant.name}</p>
                <p className="text-xs font-semibold text-hsa-secondary">{brand.assistant.nameAr}</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                className="rounded-full p-2 text-hsa-secondary hover:bg-hsa-soft hover:text-hsa-black"
                onClick={() => setExpanded((value) => !value)}
                aria-label="تغيير حجم نافذة المساعد"
              >
                <Minimize2 size={18} />
              </button>
              <button
                className="rounded-full p-2 text-hsa-secondary hover:bg-hsa-soft hover:text-hsa-black"
                onClick={() => setOpen(false)}
                aria-label="إغلاق مساعد HSAAI"
              >
                <X size={18} />
              </button>
            </div>
          </header>

          <div className="flex h-[calc(100%-4.25rem)] min-h-0 flex-col">
            <div className="border-b border-hsa-border px-4 py-3">
              <div className="flex items-center gap-2 rounded-2xl border border-hsa-yellow/30 bg-hsa-soft/70 px-3 py-2 text-xs text-hsa-black">
                <ShieldCheck size={15} className="shrink-0 text-hsa-gold" />
                <span>بيئة داخلية آمنة — يتم احترام الصلاحيات وسجلات التدقيق.</span>
              </div>
            </div>

            <div ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain bg-hsa-bg px-4 py-4">
              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={message.role === "user" ? "text-left" : "text-right"}>
                  <div
                    className={[
                      "inline-block max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-7",
                      message.role === "user"
                        ? "border border-hsa-border bg-white text-hsa-black shadow-hsa-card"
                        : "border border-hsa-yellow/30 bg-hsa-soft text-hsa-black",
                    ].join(" ")}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    {message.agent && (
                      <span className="mt-2 block text-micro font-semibold text-hsa-gold">Agent: {message.agent}</span>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex items-center gap-2 text-xs text-hsa-secondary">
                  <Sparkles size={15} className="animate-pulse text-hsa-gold" />
                  HSAAI يكتب الإجابة...
                </div>
              )}
            </div>

            <div className="border-t border-hsa-border bg-white p-3">
              <div className="mb-3 flex flex-wrap gap-2">
                {quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => submit(prompt)}
                    className="rounded-full border border-hsa-yellow/30 bg-hsa-soft px-3 py-1.5 text-xs font-semibold text-hsa-gold hover:bg-hsa-yellow hover:text-hsa-black"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
              <div className="flex items-end gap-2 rounded-2xl border border-hsa-border bg-hsa-bg px-3 py-2">
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      submit();
                    }
                  }}
                  placeholder="اكتب استفسارك هنا..."
                  className="min-h-10 flex-1 resize-none bg-transparent px-1 py-2 text-[16px] text-hsa-black outline-none placeholder:text-hsa-secondary/70 sm:text-sm"
                  rows={1}
                />
                <Button
                  onClick={() => submit()}
                  disabled={loading || !input.trim()}
                  className="h-10 w-10 rounded-full p-0"
                  aria-label="إرسال إلى HSAAI"
                >
                  <Send size={17} />
                </Button>
              </div>
            </div>
          </div>
        </section>
      )}

      <button
        onClick={openNewChat}
        className="group relative flex h-16 w-16 items-center justify-center sm:h-[72px] sm:w-[72px] rounded-full bg-hsa-yellow text-hsa-black shadow-hsa-gold transition hover:scale-105 hover:bg-hsa-gold-dark hover:text-white focus:outline-none focus:ring-4 focus:ring-hsa-gold/30"
        aria-label="فتح دردشة جديدة في HSAAI Assistant"
        title="فتح دردشة جديدة"
      >
        <span className="absolute -top-1 -start-1 flex h-5 w-5 items-center justify-center rounded-full bg-hsa-black text-nano font-semibold text-hsa-yellow ring-4 ring-white">
          AI
        </span>
        <span className="absolute inset-0 rounded-full border border-hsa-gold/40 animate-ping" />
        <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt={brand.assistant.name} className="relative z-10 h-12 w-12 rounded-full object-cover sm:h-[58px] sm:w-[58px]" />
      </button>
    </div>
  );
}
