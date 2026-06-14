"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ChatActions, ChatMessage } from "@/lib/types";

interface Props {
  onAfterResponse: () => void;
}

const SUGGESTIONS = [
  "How is my portfolio doing?",
  "Buy 5 shares of NVDA",
  "What's my riskiest position?",
];

export default function ChatPanel({ onAfterResponse }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getChatHistory().then(setMessages).catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || loading) return;
    setDraft("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setLoading(true);
    try {
      const res = await api.sendChat(message);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: res.message, actions: res.actions },
      ]);
      onAfterResponse();
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Something went wrong.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-title flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-purple" />
        FinAlly Assistant
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.length === 0 && !loading && (
          <div className="space-y-2 text-sm text-muted">
            <p>Ask me to analyze your portfolio or execute trades.</p>
            <div className="flex flex-col gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded border border-border px-2 py-1 text-left text-xs hover:border-blue hover:text-gray-200"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}

        {loading && (
          <div className="flex items-center gap-1 text-sm text-muted">
            <Dot /> <Dot delay={150} /> <Dot delay={300} />
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
        className="flex gap-2 border-t border-border p-2"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask FinAlly…"
          className="input w-full"
          disabled={loading}
          aria-label="Chat message"
        />
        <button type="submit" className="btn-submit shrink-0" disabled={loading || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-blue/20 text-gray-100"
            : "bg-panel-alt border border-border text-gray-200"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {message.actions && <ActionList actions={message.actions} />}
      </div>
    </div>
  );
}

function ActionList({ actions }: { actions: ChatActions }) {
  const hasAny =
    actions.trades.length > 0 || actions.watchlist_changes.length > 0;
  if (!hasAny) return null;
  return (
    <div className="mt-2 space-y-1 border-t border-border pt-2 text-xs">
      {actions.trades.map((t, i) => (
        <div
          key={`t${i}`}
          className={t.status === "rejected" ? "text-down" : "text-up"}
        >
          {t.status === "rejected"
            ? `✕ ${t.side} ${t.quantity} ${t.ticker} — ${t.error}`
            : `✓ ${t.side} ${t.quantity} ${t.ticker} @ ${t.price}`}
        </div>
      ))}
      {actions.watchlist_changes.map((w, i) => (
        <div
          key={`w${i}`}
          className={w.status === "rejected" ? "text-down" : "text-blue"}
        >
          {w.status === "rejected"
            ? `✕ ${w.action} ${w.ticker} — ${w.error}`
            : `✓ watchlist ${w.action}: ${w.ticker}`}
        </div>
      ))}
    </div>
  );
}

function Dot({ delay = 0 }: { delay?: number }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-muted"
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}
