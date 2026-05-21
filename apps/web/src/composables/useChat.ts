import { computed, onMounted, onUnmounted, ref } from "vue";

import * as api from "../lib/api";
import type { Message, Session } from "../types/chat";
import { messageFromError } from "../utils/errors";

function createOptimisticUserMessage(sessionId: string, content: string): Message {
  return {
    id: `optimistic-${crypto.randomUUID()}`,
    sessionId,
    role: "user",
    content,
    createdAt: new Date().toISOString(),
  };
}

export function useChat() {
  const sessions = ref<Session[]>([]);
  const messages = ref<Message[]>([]);
  const selectedSessionId = ref<string | null>(null);
  const loading = ref(true);
  const activatingMessageId = ref<string | null>(null);
  const loadingOlderMessages = ref(false);
  const messagesHasMore = ref(false);
  const messagesNextBefore = ref<string | null>(null);
  const regeneratingMessageId = ref<string | null>(null);
  const sending = ref(false);
  const error = ref<string | null>(null);
  const status = ref<string | null>(null);

  const activeSession = computed(() =>
    sessions.value.find((session) => session.id === selectedSessionId.value),
  );
  const draftKey = computed(() =>
    selectedSessionId.value
      ? `careerpilot.draft.s.${selectedSessionId.value}`
      : `careerpilot.draft.new.${windowDraftId()}`,
  );

  onMounted(async () => {
    await loadSessions();
    const routeSessionId = sessionIdFromPath();
    if (routeSessionId) {
      await selectSession(routeSessionId, { replaceUrl: true });
    }
    window.addEventListener("popstate", handlePopState);
  });

  onUnmounted(() => {
    window.removeEventListener("popstate", handlePopState);
  });

  async function handlePopState() {
    const routeSessionId = sessionIdFromPath();
    if (routeSessionId) {
      await selectSession(routeSessionId, { skipUrl: true });
    } else {
      newSession({ skipUrl: true });
    }
  }

  async function loadSessions() {
    loading.value = true;
    error.value = null;
    status.value = null;
    try {
      const response = await api.listSessions();
      sessions.value = response.sessions;
    } catch (err) {
      error.value = messageFromError(err);
    } finally {
      loading.value = false;
    }
  }

  async function selectSession(
    sessionId: string,
    options: { replaceUrl?: boolean; skipUrl?: boolean } = {},
  ) {
    selectedSessionId.value = sessionId;
    error.value = null;
    status.value = null;
    messagesHasMore.value = false;
    messagesNextBefore.value = null;
    try {
      const response = await api.listMessages(sessionId, { limit: 15 });
      messages.value = response.messages;
      messagesHasMore.value = response.page.hasMore;
      messagesNextBefore.value = response.page.nextBefore;
      if (!options.skipUrl) {
        writeSessionPath(sessionId, { replace: options.replaceUrl });
      }
    } catch (err) {
      error.value = messageFromError(err);
      selectedSessionId.value = null;
      messages.value = [];
      messagesHasMore.value = false;
      messagesNextBefore.value = null;
      if (!options.skipUrl) {
        writeRootPath({ replace: true });
      }
    }
  }

  function newSession(options: { skipUrl?: boolean } = {}) {
    error.value = null;
    status.value = null;
    selectedSessionId.value = null;
    messages.value = [];
    messagesHasMore.value = false;
    messagesNextBefore.value = null;
    if (!options.skipUrl) {
      writeRootPath();
    }
  }

  async function deleteSession(sessionId: string) {
    error.value = null;
    status.value = null;
    try {
      await api.deleteSession(sessionId);
      const remainingSessions = sessions.value.filter((session) => session.id !== sessionId);
      sessions.value = remainingSessions;

      if (selectedSessionId.value !== sessionId) {
        return;
      }

      const nextSession = remainingSessions[0];
      if (nextSession) {
        await selectSession(nextSession.id, { replaceUrl: true });
      } else {
        newSession();
      }
    } catch (err) {
      error.value = messageFromError(err);
    }
  }

  async function renameSession(sessionId: string, title: string) {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      error.value = "Title is required";
      return;
    }

    error.value = null;
    status.value = null;
    try {
      const response = await api.updateSessionTitle(sessionId, trimmedTitle);
      sessions.value = sessions.value.map((session) =>
        session.id === sessionId ? response.session : session,
      );
    } catch (err) {
      error.value = messageFromError(err);
    }
  }

  async function loadOlderMessages() {
    const sessionId = selectedSessionId.value;
    if (
      !sessionId ||
      !messagesHasMore.value ||
      !messagesNextBefore.value ||
      loadingOlderMessages.value
    ) {
      return;
    }

    loadingOlderMessages.value = true;
    error.value = null;
    try {
      const response = await api.listMessages(sessionId, {
        limit: 15,
        before: messagesNextBefore.value,
      });
      messages.value = [...response.messages, ...messages.value];
      messagesHasMore.value = response.page.hasMore;
      messagesNextBefore.value = response.page.nextBefore;
    } catch (err) {
      error.value = messageFromError(err);
    } finally {
      loadingOlderMessages.value = false;
    }
  }

  function setStatus(message: string | null) {
    status.value = message;
  }

  async function sendMessage(content: string) {
    const trimmedContent = content.trim();
    if (!trimmedContent || sending.value) {
      return;
    }

    sending.value = true;
    error.value = null;

    try {
      if (!selectedSessionId.value) {
        const response = await api.createSession();
        sessions.value = [response.session, ...sessions.value];
        selectedSessionId.value = response.session.id;
        writeSessionPath(response.session.id);
      }

      const sessionId = selectedSessionId.value;
      if (!sessionId) {
        throw new Error("No active session");
      }

      const optimisticMessage = createOptimisticUserMessage(sessionId, trimmedContent);
      messages.value = [...messages.value, optimisticMessage];

      const response = await api.sendUserMessage(sessionId, trimmedContent);
      const responseMessages = response.messages ?? [response.message];
      messages.value = messages.value.flatMap((message) =>
        message.id === optimisticMessage.id ? responseMessages : [message],
      );
      await loadSessions();
      selectedSessionId.value = sessionId;
    } catch (err) {
      error.value = messageFromError(err);
      if (selectedSessionId.value) {
        await selectSession(selectedSessionId.value);
      }
    } finally {
      sending.value = false;
    }
  }

  async function regenerateMessage(messageId: string) {
    const sessionId = selectedSessionId.value;
    if (!sessionId || sending.value || regeneratingMessageId.value) {
      return;
    }

    regeneratingMessageId.value = messageId;
    error.value = null;

    try {
      const response = await api.regenerateMessage(sessionId, messageId);
      messages.value = [...messages.value, response.message];
      await loadSessions();
      selectedSessionId.value = sessionId;
    } catch (err) {
      error.value = messageFromError(err);
    } finally {
      regeneratingMessageId.value = null;
    }
  }

  async function activateMessage(messageId: string) {
    const sessionId = selectedSessionId.value;
    if (!sessionId || activatingMessageId.value) {
      return;
    }

    activatingMessageId.value = messageId;
    error.value = null;

    try {
      const response = await api.activateMessage(sessionId, messageId);
      const parentMessageId = response.message.parentMessageId;
      messages.value = messages.value.map((message) =>
        parentMessageId && message.id === parentMessageId
          ? { ...message, activeResponseId: response.message.id }
          : message,
      );
    } catch (err) {
      error.value = messageFromError(err);
    } finally {
      activatingMessageId.value = null;
    }
  }

  return {
    activatingMessageId,
    activeSession,
    error,
    loading,
    loadingOlderMessages,
    messages,
    messagesHasMore,
    regeneratingMessageId,
    selectedSessionId,
    sending,
    sessions,
    status,
    loadSessions,
    activateMessage,
    loadOlderMessages,
    deleteSession,
    renameSession,
    regenerateMessage,
    setStatus,
    selectSession,
    sendMessage,
    newSession,
    draftKey,
  };
}

function sessionIdFromPath() {
  const match = window.location.pathname.match(/^\/s\/([^/]+)\/?$/);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

function writeSessionPath(sessionId: string, options: { replace?: boolean } = {}) {
  const path = `/s/${encodeURIComponent(sessionId)}`;
  writePath(path, options);
}

function writeRootPath(options: { replace?: boolean } = {}) {
  writePath("/", options);
}

function writePath(path: string, options: { replace?: boolean } = {}) {
  if (window.location.pathname === path) {
    return;
  }

  const method = options.replace ? "replaceState" : "pushState";
  window.history[method](null, "", path);
}

function windowDraftId() {
  const key = "careerpilot.window.id";
  const existing = window.sessionStorage.getItem(key);
  if (existing) {
    return existing;
  }

  const id = crypto.randomUUID();
  window.sessionStorage.setItem(key, id);
  return id;
}
