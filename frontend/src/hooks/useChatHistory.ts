import { useCallback, useEffect, useMemo, useState } from "react";

import { makeId, makeTitleFromFirstUserMessage } from "../lib/id";
import type { Chat, ChatMessage } from "../types/chat";

const STORAGE_KEY = "mas_chat_history_v1";

type Persisted = {
  chats: Chat[];
  activeChatId: string | null;
};

function loadPersisted(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { chats: [], activeChatId: null };
    const parsed = JSON.parse(raw) as Persisted;
    if (!parsed || !Array.isArray(parsed.chats)) return { chats: [], activeChatId: null };
    return {
      chats: parsed.chats,
      activeChatId: parsed.activeChatId ?? null,
    };
  } catch {
    return { chats: [], activeChatId: null };
  }
}

function savePersisted(state: Persisted) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function useChatHistory() {
  const [{ chats, activeChatId }, setState] = useState<Persisted>(() => ({
    chats: [],
    activeChatId: null,
  }));

  useEffect(() => {
    const initial = loadPersisted();
    setState(initial);
  }, []);

  useEffect(() => {
    // persist after initial load
    if (chats) savePersisted({ chats, activeChatId });
  }, [chats, activeChatId]);

  const activeChat = useMemo(() => {
    const id = activeChatId ?? chats[0]?.id ?? null;
    return chats.find((c) => c.id === id) ?? null;
  }, [chats, activeChatId]);

  const createNewChat = useCallback(() => {
    const now = Date.now();
    const chat: Chat = {
      id: makeId("chat"),
      title: "New chat",
      createdAt: now,
      updatedAt: now,
      messages: [],
    };

    setState((s) => ({
      chats: [chat, ...s.chats],
      activeChatId: chat.id,
    }));

    return chat.id;
  }, []);

  const setActiveChatId = useCallback((chatId: string) => {
    setState((s) => ({ ...s, activeChatId: chatId }));
  }, []);

  const deleteChat = useCallback((chatId: string) => {
    setState((s) => {
      const remaining = s.chats.filter((c) => c.id !== chatId);
      const nextActive =
        s.activeChatId === chatId ? remaining[0]?.id ?? null : s.activeChatId;
      return { chats: remaining, activeChatId: nextActive };
    });
  }, []);

  const clearChat = useCallback((chatId: string) => {
    setState((s) => ({
      ...s,
      chats: s.chats.map((c) =>
        c.id === chatId
          ? { ...c, messages: [], title: "New chat", updatedAt: Date.now() }
          : c,
      ),
    }));
  }, []);

  const upsertMessage = useCallback((chatId: string, msg: ChatMessage) => {
    setState((s) => ({
      ...s,
      chats: s.chats.map((c) => {
        if (c.id !== chatId) return c;

        const exists = c.messages.some((m) => m.id === msg.id);
        const messages = exists
          ? c.messages.map((m) => (m.id === msg.id ? msg : m))
          : [...c.messages, msg];

        const updatedAt = Math.max(c.updatedAt, msg.createdAt);

        // auto-title from first user message
        let title = c.title;
        if ((c.title === "New chat" || !c.title) && msg.role === "user") {
          title = makeTitleFromFirstUserMessage(msg.content);
        }

        return { ...c, messages, title, updatedAt };
      }),
    }));
  }, []);

  const replaceMessages = useCallback((chatId: string, messages: ChatMessage[]) => {
    setState((s) => ({
      ...s,
      chats: s.chats.map((c) =>
        c.id === chatId
          ? {
              ...c,
              messages,
              updatedAt: messages[messages.length - 1]?.createdAt ?? Date.now(),
              title:
                c.title === "New chat" && messages.find((m) => m.role === "user")
                  ? makeTitleFromFirstUserMessage(
                      messages.find((m) => m.role === "user")!.content,
                    )
                  : c.title,
            }
          : c,
      ),
    }));
  }, []);

  return {
    chats,
    activeChat,
    activeChatId: activeChat?.id ?? null,
    createNewChat,
    setActiveChatId,
    deleteChat,
    clearChat,
    upsertMessage,
    replaceMessages,
  };
}
