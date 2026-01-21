import { useEffect, useRef, useState } from "react";

export function Composer({
  disabled,
  onSend,
}: {
  disabled?: boolean;
  onSend: (text: string) => void;
}) {
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!disabled) taRef.current?.focus();
  }, [disabled]);

  const send = () => {
    const text = value.trim();
    if (!text) return;
    onSend(text);
    setValue("");
  };

  return (
    <div className="border-t border-border bg-surface px-4 py-3">
      <div className="mx-auto flex max-w-[980px] items-end gap-3">
        <div className="flex-1">
          <textarea
            ref={taRef}
            className="min-h-[48px] w-full resize-none rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text shadow-ib placeholder:text-faint focus:border-accent focus:outline-none"
            placeholder="Ask anything"
            value={value}
            disabled={disabled}
            rows={1}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!disabled) send();
              }
            }}
          />
          <div className="mt-2 text-[12px] text-faint">
            Enter to send • Shift+Enter for newline
          </div>
        </div>
        <button
          type="button"
          className="h-[48px] shrink-0 rounded-lg bg-accent px-4 text-sm font-semibold text-white shadow-ib hover:bg-accentHover disabled:cursor-not-allowed disabled:opacity-50"
          onClick={send}
          disabled={disabled || !value.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
