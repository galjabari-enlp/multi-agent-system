import { useEffect, useMemo, useRef, useState } from "react";

import type { ChatMessage } from "../types/chat";
import { MessageBubble } from "./MessageBubble";

export function ChatThread({
  messages,
  onRetry,
}: {
  messages: ChatMessage[];
  onRetry: (messageText: string) => void;
}) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [isPinnedToBottom, setIsPinnedToBottom] = useState(true);

  const jumpToLatest = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  };

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;

    const onScroll = () => {
      const threshold = 120;
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      setIsPinnedToBottom(distanceFromBottom < threshold);
    };

    onScroll();
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (isPinnedToBottom) jumpToLatest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length]);

  const hasMessages = messages.length > 0;
  const intro = useMemo(() => {
    return (
      <div className="mx-auto mt-24 max-w-[980px] px-4">
        <div className="text-center">
          <div className="text-3xl font-semibold tracking-tight text-text">
            What's on the agenda today?
          </div>
          <div className="mt-3 text-sm text-muted">
            Ask for research, competitor analysis, or a market memo.
          </div>
        </div>
      </div>
    );
  }, []);

  return (
    <div className="relative flex-1 overflow-hidden">
      <div ref={scrollerRef} className="h-full overflow-y-auto">
        {!hasMessages ? (
          intro
        ) : (
          <div className="mx-auto flex max-w-[980px] flex-col gap-3 px-4 py-6">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} onRetry={onRetry} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {!isPinnedToBottom && hasMessages ? (
        <div className="pointer-events-none absolute bottom-6 left-0 right-0">
          <div className="mx-auto flex max-w-[980px] justify-center px-4">
            <button
              type="button"
              className="pointer-events-auto rounded-full border border-border bg-surface2 px-4 py-2 text-xs text-text shadow-ib hover:border-accent"
              onClick={jumpToLatest}
            >
              Jump to latest
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
