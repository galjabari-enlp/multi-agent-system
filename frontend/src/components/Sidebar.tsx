import type { Chat } from "../types/chat";

function IconMark() {
  return (
    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-white shadow-ib">
      <span className="text-sm font-bold">IB</span>
    </div>
  );
}

export function Sidebar({
  chats,
  activeChatId,
  onNewChat,
  onSelectChat,
  onDeleteChat,
}: {
  chats: Chat[];
  activeChatId: string | null;
  onNewChat: () => void;
  onSelectChat: (chatId: string) => void;
  onDeleteChat: (chatId: string) => void;
}) {
  return (
    <aside className="flex h-full w-[280px] flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-3 border-b border-border px-4 py-4">
        <IconMark />
        <div className="leading-tight">
          <div className="text-sm font-semibold text-text">Multi-Agent</div>
          <div className="text-xs text-faint">IBKR themed</div>
        </div>
      </div>

      <div className="px-4 py-4">
        <button
          type="button"
          className="w-full rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white shadow-ib hover:bg-accentHover"
          onClick={onNewChat}
        >
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        <div className="px-2 pb-2 text-[11px] font-semibold tracking-wide text-faint">
          CHATS
        </div>
        <ul className="space-y-1">
          {chats.map((c) => {
            const active = c.id === activeChatId;
            return (
              <li key={c.id}>
                <div
                  className={
                    active
                      ? "group flex items-center justify-between rounded-md border border-border bg-surface2 px-3 py-2 text-sm text-text shadow-ib"
                      : "group flex items-center justify-between rounded-md border border-transparent px-3 py-2 text-sm text-muted hover:border-border hover:bg-surface2"
                  }
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => onSelectChat(c.id)}
                    title={c.title}
                  >
                    <div className="truncate">{c.title}</div>
                    <div className="mt-0.5 truncate text-[11px] text-faint">
                      {new Date(c.updatedAt).toLocaleString()}
                    </div>
                  </button>

                  <button
                    type="button"
                    className="ml-2 rounded-md border border-border bg-surface2 px-2 py-1 text-[11px] text-faint opacity-0 hover:text-danger group-hover:opacity-100"
                    onClick={() => onDeleteChat(c.id)}
                    title="Delete chat"
                  >
                    Delete
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="border-t border-border px-4 py-3 text-[11px] text-faint">
        Session-local history (localStorage)
      </div>
    </aside>
  );
}
