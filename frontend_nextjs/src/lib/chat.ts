import { apiBaseUrl, parseApiErrorMessage } from "./api";

const chatBase = `${apiBaseUrl}/api/v1/chat`;

export const chatConversationStorageKey = "ai_platform_chat_conversation_id";

/** Fired when the sidebar should refetch the conversation list (same tab). */
export const CHAT_CONVERSATIONS_UPDATED_EVENT =
  "ai_platform_chat_conversations_updated";

export function notifyChatConversationsUpdated(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(CHAT_CONVERSATIONS_UPDATED_EVENT));
  }
}

export type ChatConversation = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatConversationListResult = {
  items: ChatConversation[];
  hasMore: boolean;
};

/** Page size for sidebar “Show more” (must match API default). */
export const CHAT_CONVERSATIONS_PAGE_SIZE = 15;

export type MessageBlockDto = {
  type: string;
  position: number;
  payload: Record<string, unknown>;
};

/** Matches GET …/messages items; optional fields support older API responses. */
export type ChatMessageDto = {
  id: string;
  role: "user" | "assistant";
  text: string;
  created_at?: string;
  content_format?: "markdown" | "plain";
  blocks?: MessageBlockDto[];
};

export type SendMessageResult = {
  user_message_id: string;
  assistant_message_id: string;
  assistant_text: string;
  /** Defaults to "markdown" when omitted (older API). */
  assistant_content_format?: "markdown" | "plain";
};

function authHeaders(accessToken: string): HeadersInit {
  return {
    Authorization: `Bearer ${accessToken.trim()}`,
    "Content-Type": "application/json",
  };
}

/** WebSocket URL for live Playwright screencast (JWT via query param). */
export function browserLiveWsUrl(accessToken: string): string {
  const token = encodeURIComponent(accessToken.trim());
  const explicitWs = process.env.NEXT_PUBLIC_WS_URL?.trim().replace(/\/+$/, "");
  if (explicitWs) {
    return `${explicitWs}/api/v1/chat/browser/live?token=${token}`;
  }
  const httpBase = apiBaseUrl;
  if (httpBase) {
    const wsBase = httpBase.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");
    return `${wsBase}/api/v1/chat/browser/live?token=${token}`;
  }
  return `ws://127.0.0.1:8000/api/v1/chat/browser/live?token=${token}`;
}

export async function fetchChatConversations(
  accessToken: string,
  options: { limit?: number; offset?: number } = {},
): Promise<ChatConversationListResult> {
  const limit = options.limit ?? CHAT_CONVERSATIONS_PAGE_SIZE;
  const offset = options.offset ?? 0;
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const res = await fetch(`${chatBase}/conversations?${params}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken.trim()}` },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  const data = (await res.json()) as {
    items: ChatConversation[];
    has_more: boolean;
  };
  return {
    items: data.items,
    hasMore: data.has_more,
  };
}

export async function fetchChatConversation(
  accessToken: string,
  conversationId: string,
): Promise<ChatConversation> {
  const res = await fetch(
    `${chatBase}/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${accessToken.trim()}` },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return (await res.json()) as ChatConversation;
}

export async function updateChatConversation(
  accessToken: string,
  conversationId: string,
  body: { name: string },
): Promise<ChatConversation> {
  const res = await fetch(
    `${chatBase}/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: "PUT",
      headers: authHeaders(accessToken),
      body: JSON.stringify(body),
      cache: "no-store",
    },
  );
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return (await res.json()) as ChatConversation;
}

export async function createChatConversation(
  accessToken: string,
  body: { name?: string; description?: string | null } = {},
): Promise<ChatConversation> {
  const res = await fetch(`${chatBase}/conversations`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return (await res.json()) as ChatConversation;
}

export async function fetchChatMessages(
  accessToken: string,
  conversationId: string,
): Promise<ChatMessageDto[]> {
  const res = await fetch(
    `${chatBase}/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${accessToken.trim()}` },
      cache: "no-store",
    },
  );
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return (await res.json()) as ChatMessageDto[];
}

// ── SSE streaming ────────────────────────────────────────────────────────────

export type SubagentInfo = {
  id: string;
  /** Matches toolCall.args.subagent_type from the reference. */
  subagent_type: string;
  description: string;
  status: "pending" | "running" | "complete" | "error";
  /** Streaming content while running; final result when complete. */
  content: string;
  result: string | undefined;
  started_at: number | undefined;
  completed_at: number | undefined;
};

export type TodoItem = {
  content: string
  status: "pending" | "in_progress" | "completed"
}

export type ToolCallInfo = {
  id: string
  tool_name: string
  args: Record<string, unknown>
  status: "running" | "complete" | "error"
  result: string | undefined
  started_at: number | undefined
  completed_at: number | undefined
  previewImageBase64?: string
  previewUrl?: string
}

export type StreamEvent =
  | { type: "start"; user_message_id: string }
  | { type: "token"; content: string }
  | { type: "subagent_start"; id: string; subagent_type: string; description: string; started_at: number }
  | { type: "subagent_token"; id: string; content: string }
  | { type: "subagent_done"; id: string; result: string; status: "complete" | "error"; completed_at: number }
  | { type: "tool_call_start"; id: string; tool_name: string; args: Record<string, unknown>; started_at: number }
  | { type: "tool_call_end"; id: string; tool_name: string; result: string; status: "complete" | "error"; completed_at: number }
  | { type: "browser_preview"; tool_call_id: string; url: string; image_base64: string }
  | { type: "todos_update"; todos: TodoItem[] }
  | { type: "interrupt"; pending_tool_calls: { tool_name: string; args: Record<string, unknown>; description: string }[] }
  | { type: "saved"; assistant_message_id: string; assistant_text: string; assistant_blocks?: MessageBlockDto[]; interrupted: boolean }
  | { type: "error"; message: string };

export async function* streamChatMessage(
  accessToken: string,
  conversationId: string,
  text: string,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(
    `${chatBase}/conversations/${encodeURIComponent(conversationId)}/messages/stream`,
    {
      method: "POST",
      headers: authHeaders(accessToken),
      body: JSON.stringify({ text: text.trim() }),
      cache: "no-store",
    },
  );

  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") return;
        try {
          yield JSON.parse(raw) as StreamEvent;
        } catch {
          // malformed line — skip
        }
      }
    }
  } finally {
    reader.cancel();
  }
}

export async function sendChatMessage(
  accessToken: string,
  conversationId: string,
  text: string,
): Promise<SendMessageResult> {
  const controller = new AbortController();
  const timeoutMs = 45000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(
      `${chatBase}/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: "POST",
        headers: authHeaders(accessToken),
        body: JSON.stringify({ text: text.trim() }),
        cache: "no-store",
        signal: controller.signal,
      },
    );
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        "Assistant response timed out. Retrying message sync from server.",
      );
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
  if (!res.ok) {
    throw new Error(await parseApiErrorMessage(res));
  }
  return (await res.json()) as SendMessageResult;
}
