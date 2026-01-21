export type Role = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  error?: {
    kind: "network" | "timeout" | "http" | "unknown";
    message: string;
    retryPayload?: { message: string };
  };
};

export type Chat = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
};
