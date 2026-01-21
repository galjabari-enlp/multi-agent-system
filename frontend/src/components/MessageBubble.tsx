import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

import type { ChatMessage } from "../types/chat";

function CopyButton({ text }: { text: string }) {
  return (
    <button
      type="button"
      className="rounded-md border border-border bg-surface2 px-2 py-1 text-xs text-muted hover:border-accent hover:text-text"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
      }}
    >
      Copy
    </button>
  );
}

export function MessageBubble({
  message,
  onRetry,
}: {
  message: ChatMessage;
  onRetry?: (messageText: string) => void;
}) {
  const isUser = message.role === "user";

  return (
    <div className={isUser ? "w-full" : "w-full"}>
      <div
        className={
          isUser
            ? "ml-auto max-w-[820px] rounded-lg border border-border bg-surface2 px-4 py-3 text-sm text-text shadow-ib"
            : "mr-auto max-w-[820px] rounded-lg border border-border bg-surface px-4 py-3 text-sm text-text shadow-ib"
        }
      >
        <div className="flex items-start justify-between gap-3">
          <div className={isUser ? "whitespace-pre-wrap" : "w-full"}>
            {isUser ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              <div className="prose prose-invert prose-sm">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || "");
                      const code = String(children).replace(/\n$/, "");
                      return match ? (
                        <SyntaxHighlighter
                          {...props}
                          style={oneDark}
                          language={match[1]}
                          PreTag="div"
                          customStyle={{
                            background: "#0d1117",
                            border: "1px solid #1f2a35",
                            borderRadius: 10,
                            padding: 12,
                            margin: 0,
                          }}
                        >
                          {code}
                        </SyntaxHighlighter>
                      ) : (
                        <code
                          {...props}
                          className="rounded bg-codeBg px-1 py-0.5 font-mono text-[12px]"
                        >
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>

          {!isUser && (
            <div className="flex shrink-0 flex-col items-end gap-2">
              <CopyButton text={message.content} />
              {message.error?.retryPayload?.message && onRetry ? (
                <button
                  type="button"
                  className="rounded-md border border-border bg-surface2 px-2 py-1 text-xs text-danger hover:border-danger"
                  onClick={() => onRetry(message.error!.retryPayload!.message)}
                >
                  Retry
                </button>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
