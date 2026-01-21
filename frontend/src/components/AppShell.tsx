import { useMemo, useRef, useState } from "react";

import { ChatThread } from "./ChatThread";
import { Composer } from "./Composer";
import { Sidebar } from "./Sidebar";
import { Spinner } from "./Spinner";
import { ApiError, postChat } from "../lib/apiClient";
import { makeId } from "../lib/id";
import { useChatHistory } from "../hooks/useChatHistory";
import type { ChatMessage } from "../types/chat";

export function AppShell() {
  const {
    chats,
    activeChat,
    activeChatId,
    createNewChat,
    setActiveChatId,
    deleteChat,
    clearChat,
    upsertMessage,
  } = useChatHistory();

  const [isSending, setIsSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const ensuredChatId = useMemo(() => {
    if (activeChatId) return activeChatId;
    return createNewChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChatId]);

  const messages = activeChat?.messages ?? [];

  const sendMessage = async (text: string) => {
    const chatId = ensuredChatId;

    // optimistic user message
    const userMsg: ChatMessage = {
      id: makeId("msg"),
      role: "user",
      content: text,
      createdAt: Date.now(),
    };
    upsertMessage(chatId, userMsg);

    const thinkingMsgId = makeId("msg");
    upsertMessage(chatId, {
      id: thinkingMsgId,
      role: "assistant",
      content: "Assistant is thinking…",
      createdAt: Date.now() + 1,
    });

    setIsSending(true);
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const res = await postChat({
        message: text,
        chatId,
        signal: abortRef.current.signal,
      });

      upsertMessage(chatId, {
        id: thinkingMsgId,
        role: "assistant",
        content: res.reply,
        createdAt: Date.now() + 2,
      });
    } catch (e: unknown) {
      const errText =
        e instanceof ApiError
          ? e.message + (e.bodyText ? `\n\n${e.bodyText}` : "")
          : e instanceof Error
            ? e.message
            : "Unknown error";

      upsertMessage(chatId, {
        id: thinkingMsgId,
        role: "assistant",
        content: `**Error**\n\n${errText}`,
        createdAt: Date.now() + 2,
        error: {
          kind: e instanceof ApiError && e.message.includes("timeout") ? "timeout" : "unknown",
          message: errText,
          retryPayload: { message: text },
        },
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex h-screen w-screen bg-bg text-text">
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onNewChat={() => {
          const id = createNewChat();
          setActiveChatId(id);
        }}
        onSelectChat={(id) => setActiveChatId(id)}
        onDeleteChat={(id) => deleteChat(id)}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-text">
              {activeChat?.title ?? "New chat"}
            </div>
            <div className="mt-0.5 text-[11px] text-faint">
              Backend: {import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isSending ? (
              <div className="flex items-center gap-2 text-xs text-muted">
                <Spinner size={14} />
                <span>Working</span>
              </div>
            ) : null}

            <button
              type="button"
              className="rounded-md border border-border bg-surface2 px-3 py-2 text-xs text-muted hover:border-accent hover:text-text"
              onClick={() => {
                if (!activeChatId) return;
                clearChat(activeChatId);
              }}
              disabled={!activeChatId}
            >
              Clear
            </button>
          </div>
        </header>

        <ChatThread messages={messages} onRetry={(msg) => sendMessage(msg)} />

        <div className="sticky bottom-0">
          <Composer disabled={isSending} onSend={sendMessage} />
        </div>
      </main>
    </div>
  );
}
