
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
      listRef.current?.scrollTo({
        top: listRef.current.scrollHeight,
        behavior: "smooth",
      });
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

    if (!value || loading) {
      return;
    }

    setInput("");
    setOpen(true);

    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: value,
      },
    ]);

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
          content:
            response?.response ||
            "تم استلام طلبك، لكن لم تصل استجابة واضحة من الخدمة.",
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
    <div
      className="fixed bottom-[calc(1rem+env(safe-area-inset-bottom))] left-4 z-[80] print:hidden sm:bottom-6 sm:left-6"
      dir="rtl"
      aria-live="polite"
    >
      {open && (
        <section
          className={[
            "mb-4 overflow-hidden rounded-[1.6rem] border border-hsa-yellow/40 bg-hsa-black/95 text-white shadow-2xl shadow-black/40 backdrop-blur-xl",
            expanded
              ? "h-[min(78dvh,720px)] w-[min(94vw,680px)]"
              : "h-[min(72dvh,560px)] w-[min(94vw,420px)]",
          ].join(" ")}
          role="dialog"
          aria-label="مساعد HSAAI السريع"
        >
          <header className="flex items-center justify-between border-b border-hsa-yellow/20 bg-hsa-yellow px-4 py-3 text-black">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-black/20 bg-black shadow-inner">
                <Image
                  src={brand.assistant.iconPath}
                  alt={brand.assistant.name}
                  width={40}
                  height={40}
                  className="h-full w-full object-cover"
                />
              </div>

              <div>
                <p className="text-sm font-black">
                  {brand.assistant.name}
                </p>
                <p className="text-xs font-semibold text-black/70">
                  {brand.assistant.nameAr}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                className="rounded-full p-2 text-black hover:bg-black/10"
                onClick={() => setExpanded((value) => !value)}
                aria-label="تغيير حجم نافذة المساعد"
              >
                <Minimize2 size={18} />
              </button>

              <button
                type="button"
                className="rounded-full p-2 text-black hover:bg-black/10"
                onClick={() => setOpen(false)}
                aria-label="إغلاق مساعد HSAAI"
              >
                <X size={18} />
              </button>
            </div>
          </header>

          <div className="flex h-[calc(100%-4.25rem)] min-h-0 flex-col">
            <div className="border-b border-white/10 px-4 py-3">
              <div className="flex items-center gap-2 rounded-2xl border border-hsa-yellow/20 bg-hsa-yellow/10 px-3 py-2 text-xs text-slate-100">
                <ShieldCheck
                  size={15}
                  className="text-hsa-yellow"
                />

                <span>
                  بيئة داخلية آمنة — يتم احترام الصلاحيات وسجلات التدقيق.
                </span>
              </div>
            </div>

            <div
              ref={listRef}
              className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-4 py-4"
            >
              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={
                    message.role === "user"
                      ? "text-left"
                      : "text-right"
                  }
                >
                  <div
                    className={[
                      "inline-block max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-7",
                      message.role === "user"
                        ? "bg-hsa-yellow text-black"
                        : "border border-white/10 bg-white/[0.06] text-slate-100",
                    ].join(" ")}
                  >
                    <p className="whitespace-pre-wrap">
                      {message.content}
                    </p>

                    {message.agent && (
                      <span className="mt-2 block text-[11px] font-bold text-hsa-yellow">
                        Agent: {message.agent}
                      </span>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex items-center gap-2 text-xs text-slate-300">
                  <Sparkles
                    size={15}
                    className="animate-pulse text-hsa-yellow"
                  />
                  HSAAI يكتب الإجابة...
                </div>
              )}
            </div>

            <div className="border-t border-white/10 p-3">
              <div className="mb-3 flex flex-wrap gap-2">
                {quickPrompts.map((prompt) => (
                  <button
                    type="button"
                    key={prompt}
                    onClick={() => submit(prompt)}
                    className="rounded-full border border-hsa-yellow/20 bg-hsa-yellow/10 px-3 py-1.5 text-xs text-hsa-yellow hover:bg-hsa-yellow hover:text-black"
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              <div className="flex items-end gap-2 rounded-2xl border border-white/10 bg-black px-3 py-2">
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey
                    ) {
                      event.preventDefault();
                      void submit();
                    }
                  }}
                  placeholder="اكتب استفسارك هنا..."
                  className="min-h-10 flex-1 resize-none bg-transparent px-1 py-2 text-[16px] text-white outline-none placeholder:text-slate-500 sm:text-sm"
                  rows={1}
                  aria-label="استفسارك"
                />

                <Button
                  type="button"
                  onClick={() => void submit()}
                  disabled={loading || !input.trim()}
                  className="h-10 w-10 rounded-full bg-hsa-yellow p-0 text-black hover:bg-white"
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
        type="button"
        onClick={openNewChat}
        className="group relative flex h-16 w-16 items-center justify-center rounded-full border-2 border-hsa-yellow bg-black text-hsa-yellow shadow-2xl shadow-hsa-yellow/20 transition hover:scale-105 hover:bg-hsa-yellow hover:text-black focus:outline-none focus:ring-4 focus:ring-hsa-yellow/30 sm:h-[72px] sm:w-[72px]"
        aria-label="فتح دردشة جديدة في HSAAI Enterprise Assistant"
        title="فتح دردشة جديدة"
      >
        <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-hsa-soft text-[10px] font-black text-black ring-4 ring-black">
          AI
        </span>

        <span className="absolute inset-0 rounded-full border border-hsa-yellow/30 animate-ping" />

        <Image
          src={brand.assistant.iconPath}
          alt={brand.assistant.name}
          width={58}
          height={58}
          className="relative z-10 h-12 w-12 rounded-full object-cover sm:h-[58px] sm:w-[58px]"
        />
      </button>
    </div>
  );
}
