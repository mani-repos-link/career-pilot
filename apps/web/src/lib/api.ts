import type { Message, Session } from "../types/chat";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

export type MessagePage = {
  hasMore: boolean;
  nextBefore: string | null;
};

export async function listSessions() {
  return request<{ sessions: Session[] }>("/api/sessions");
}

export async function createSession(title = "New chat") {
  return request<{ session: Session }>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function deleteSession(sessionId: string) {
  return request<void>(`/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function updateSessionTitle(sessionId: string, title: string) {
  return request<{ session: Session }>(`/api/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function listMessages(
  sessionId: string,
  options: { limit?: number; before?: string } = {},
) {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 15));
  if (options.before) {
    params.set("before", options.before);
  }

  return request<{ messages: Message[]; page: MessagePage }>(
    `/api/sessions/${sessionId}/messages?${params.toString()}`,
  );
}

export async function sendUserMessage(sessionId: string, content: string) {
  return request<{ message: Message; messages?: Message[] }>(
    `/api/sessions/${sessionId}/messages`,
    {
      method: "POST",
      body: JSON.stringify({ role: "user", content }),
    },
  );
}

export async function regenerateMessage(sessionId: string, messageId: string) {
  return request<{ message: Message }>(
    `/api/sessions/${sessionId}/messages/${messageId}/regenerate`,
    {
      method: "POST",
    },
  );
}

export async function activateMessage(sessionId: string, messageId: string) {
  return request<{ message: Message }>(
    `/api/sessions/${sessionId}/messages/${messageId}/activate`,
    {
      method: "POST",
    },
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");

  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers,
  });

  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.error ?? `Request failed with ${response.status}`);
  }
  return payload as T;
}
