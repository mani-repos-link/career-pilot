<script setup lang="ts">
import { Check, ChevronLeft, ChevronRight, Copy, FileText, RefreshCw } from "lucide-vue-next";
import { computed, nextTick, ref, watch } from "vue";
import MessageContent from "./MessageContent.vue";
import type { Message } from "../../types/chat";
import { formatTime } from "../../utils/date";

const COLLAPSE_MESSAGE_LENGTH = 1000;
const COLLAPSE_MESSAGE_LINES = 20;

const props = defineProps<{
  activatingMessageId: string | null;
  hasOlderMessages: boolean;
  loadingOlderMessages: boolean;
  messages: Message[];
  regeneratingMessageId: string | null;
  sending: boolean;
  sessionId: string | null;
}>();

const emit = defineEmits<{
  activateMessage: [messageId: string];
  loadOlderMessages: [];
  regenerateMessage: [messageId: string];
}>();

type MessageEntry = {
  alternatives: Message[];
  message: Message;
  type: "message";
};

const messageListElement = ref<HTMLElement | null>(null);
const copiedAction = ref<string | null>(null);
const expandedMessageIds = ref<Set<string>>(new Set());
const preserveScrollPosition = ref(false);
let copiedActionTimeout: number | undefined;

const messageEntries = computed<MessageEntry[]>(() => {
  const visibleMessageIds = new Set(props.messages.map((message) => message.id));
  const parentIds = new Set(
    props.messages
      .map((message) => message.parentMessageId)
      .filter(
        (parentMessageId): parentMessageId is string =>
          typeof parentMessageId === "string" && visibleMessageIds.has(parentMessageId),
      ),
  );
  const alternativesByParent = new Map<string, Message[]>();

  for (const message of props.messages) {
    if (message.role.toLowerCase() !== "assistant" || !message.parentMessageId) {
      continue;
    }

    alternativesByParent.set(message.parentMessageId, [
      ...(alternativesByParent.get(message.parentMessageId) ?? []),
      message,
    ]);
  }

  const entries: MessageEntry[] = [];
  for (const message of props.messages) {
    if (message.role.toLowerCase() === "assistant" && message.parentMessageId) {
      if (parentIds.has(message.parentMessageId)) {
        continue;
      }
    }

    entries.push({
      alternatives: [message],
      message,
      type: "message",
    });

    if (message.role.toLowerCase() !== "user") {
      continue;
    }

    const alternatives = alternativesByParent.get(message.id) ?? [];
    if (alternatives.length === 0) {
      continue;
    }

    const activeResponseId = message.activeResponseId;
    const activeIndex = Math.max(
      0,
      alternatives.findIndex((alternative) => alternative.id === activeResponseId),
    );
    entries.push({
      alternatives,
      message: alternatives[activeIndex] ?? alternatives.at(-1) ?? alternatives[0],
      type: "message",
    });
  }

  return entries;
});

function messageClass(message: Message) {
  const role = message.role.toLowerCase();
  if (role === "user") {
    return "self-end border-mint-300 bg-mint-50";
  }
  if (role === "assistant") {
    return "self-start border-line bg-panel";
  }
  return "self-start border-line bg-subtle";
}

function rendersMarkdown(message: Message) {
  return message.role.toLowerCase() !== "user";
}

function messageText(message: Message) {
  return String(message.content ?? "");
}

function readableMessageText(message: Message) {
  const text = messageText(message);
  if (!rendersMarkdown(message)) {
    return text;
  }

  return text
    .replace(/```[^\n]*\n([\s\S]*?)```/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s{0,3}>\s?/gm, "")
    .replace(/^\s*[-*_]{3,}\s*$/gm, "")
    .trim();
}

function isLongMessage(message: Message) {
  return messageText(message).length > COLLAPSE_MESSAGE_LENGTH;
}

function isExpanded(messageId: string) {
  return expandedMessageIds.value.has(messageId);
}

function toggleMessage(messageId: string) {
  const nextExpandedIds = new Set(expandedMessageIds.value);
  if (nextExpandedIds.has(messageId)) {
    nextExpandedIds.delete(messageId);
  } else {
    nextExpandedIds.add(messageId);
  }
  expandedMessageIds.value = nextExpandedIds;
}

async function copyMessage(message: Message, raw: boolean) {
  const action = raw ? "raw" : "text";
  const text = raw ? messageText(message) : readableMessageText(message);
  await writeClipboard(text);
  copiedAction.value = `${message.id}:${action}`;
  window.clearTimeout(copiedActionTimeout);
  copiedActionTimeout = window.setTimeout(() => {
    copiedAction.value = null;
  }, 1500);
}

async function writeClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function isCopied(message: Message, action: "raw" | "text") {
  return copiedAction.value === `${message.id}:${action}`;
}

function canRegenerate(message: Message) {
  return (
    !message.id.startsWith("optimistic-") &&
    (message.role.toLowerCase() === "user" || message.role.toLowerCase() === "assistant")
  );
}

function isRegenerating(message: Message) {
  return props.regeneratingMessageId === message.id;
}

function isActivating(message: Message) {
  return props.activatingMessageId === message.id;
}

function activeAlternativeIndex(entry: MessageEntry) {
  return Math.max(
    0,
    entry.alternatives.findIndex((alternative) => alternative.id === entry.message.id),
  );
}

function hasAlternatives(entry: MessageEntry) {
  return entry.alternatives.length > 1;
}

function activateAdjacentAlternative(entry: MessageEntry, direction: -1 | 1) {
  const currentIndex = activeAlternativeIndex(entry);
  const nextIndex =
    (currentIndex + direction + entry.alternatives.length) % entry.alternatives.length;
  const nextMessage = entry.alternatives[nextIndex];
  if (!nextMessage || nextMessage.id === entry.message.id) {
    return;
  }
  emit("activateMessage", nextMessage.id);
}

function requestOlderMessages() {
  if (!props.hasOlderMessages || props.loadingOlderMessages) {
    return;
  }

  const element = messageListElement.value;
  preserveScrollPosition.value = true;
  previousScrollHeight = element?.scrollHeight ?? 0;
  emit("loadOlderMessages");
}

let previousScrollHeight = 0;

function handleScroll(event: Event) {
  const element = event.currentTarget;
  if (!(element instanceof HTMLElement)) {
    return;
  }

  if (element.scrollTop <= 96) {
    requestOlderMessages();
  }
}

function scrollToLatest() {
  const element = messageListElement.value;
  if (!element) {
    return;
  }

  element.scrollTop = element.scrollHeight;
}

watch(
  () => props.sessionId,
  async () => {
    preserveScrollPosition.value = false;
    await nextTick();
    scrollToLatest();
  },
);

watch(
  () => [props.messages.length, props.sending],
  async () => {
    await nextTick();
    if (preserveScrollPosition.value) {
      return;
    }
    scrollToLatest();
  },
);

watch(
  () => props.loadingOlderMessages,
  async (loading) => {
    if (loading || !preserveScrollPosition.value) {
      return;
    }

    await nextTick();
    const element = messageListElement.value;
    if (element) {
      element.scrollTop += element.scrollHeight - previousScrollHeight;
    }
    preserveScrollPosition.value = false;
    previousScrollHeight = 0;
  },
);
</script>

<template>
  <div
    ref="messageListElement"
    class="flex min-h-0 flex-col gap-3.5 overflow-y-auto p-4 md:p-6"
    @scroll="handleScroll"
  >
    <div v-if="messages.length === 0" class="m-auto max-w-xl text-center text-muted">
      <h3 class="text-lg font-semibold text-ink">Start a local conversation</h3>
      <p class="mt-2 leading-6">
        Messages are saved through the Python API into the local SQLite database.
      </p>
    </div>

    <button
      v-if="hasOlderMessages"
      class="self-center rounded-full border border-line bg-panel px-3 py-1.5 text-[0.8125rem] font-bold text-muted hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
      type="button"
      :disabled="loadingOlderMessages"
      @click="requestOlderMessages"
    >
      {{ loadingOlderMessages ? "Loading earlier messages" : "Load earlier messages" }}
    </button>

    <article
      v-for="entry in messageEntries"
      :key="entry.message.id"
      class="flex w-full max-w-3xl min-w-0 flex-col gap-2 rounded-lg border px-4 py-3.5 text-base leading-6 shadow-sm"
      :class="messageClass(entry.message)"
    >
      <div class="min-w-0 flex flex-wrap items-center gap-x-2 gap-y-1 whitespace-normal">
        <span class="text-xs font-extrabold tracking-wide text-meta uppercase">
          {{ entry.message.role }}
        </span>
        <small v-if="entry.message.model" class="truncate text-xs text-muted">
          {{ entry.message.model }}
        </small>
      </div>
      <div class="w-full min-w-0 max-w-full">
        <p
          v-if="!rendersMarkdown(entry.message)"
          class="m-0 block min-h-6 w-full whitespace-pre-wrap break-words text-ink [overflow-wrap:anywhere]"
          :class="
            isLongMessage(entry.message) && !isExpanded(entry.message.id)
              ? 'line-clamp-[var(--message-preview-lines)]'
              : ''
          "
          :style="{ '--message-preview-lines': String(COLLAPSE_MESSAGE_LINES) }"
        >
          {{ messageText(entry.message) }}
        </p>
        <MessageContent
          v-else
          :collapsed="isLongMessage(entry.message) && !isExpanded(entry.message.id)"
          :content="messageText(entry.message)"
        />
      </div>
      <div class="flex w-full min-w-0 items-center justify-between gap-3">
        <small class="text-xs text-muted">{{ formatTime(entry.message.createdAt) }}</small>

        <div class="flex shrink-0 items-center gap-1">
          <button
            v-if="hasAlternatives(entry)"
            class="inline-flex size-8 items-center justify-center rounded-md text-muted transition hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-55"
            type="button"
            title="Previous response"
            aria-label="Previous response"
            :disabled="Boolean(activatingMessageId)"
            @click="activateAdjacentAlternative(entry, -1)"
          >
            <ChevronLeft class="size-4" />
          </button>

          <span
            v-if="hasAlternatives(entry)"
            class="min-w-8 text-center text-xs font-semibold text-muted"
          >
            {{ activeAlternativeIndex(entry) + 1 }}/{{ entry.alternatives.length }}
          </span>

          <button
            v-if="hasAlternatives(entry)"
            class="inline-flex size-8 items-center justify-center rounded-md text-muted transition hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-55"
            type="button"
            title="Next response"
            aria-label="Next response"
            :disabled="Boolean(activatingMessageId)"
            @click="activateAdjacentAlternative(entry, 1)"
          >
            <ChevronRight class="size-4" />
          </button>

          <button
            v-if="isLongMessage(entry.message)"
            class="mr-1 w-fit text-sm font-semibold text-brand underline hover:text-brand-strong"
            type="button"
            @click="toggleMessage(entry.message.id)"
          >
            {{ isExpanded(entry.message.id) ? "Read less" : "Read more" }}
          </button>

          <button
            class="inline-flex size-8 items-center justify-center rounded-md text-muted transition hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-55"
            type="button"
            title="Copy message"
            aria-label="Copy message"
            @click="copyMessage(entry.message, false)"
          >
            <Check v-if="isCopied(entry.message, 'text')" class="size-4" />
            <Copy v-else class="size-4" />
          </button>

          <button
            class="inline-flex size-8 items-center justify-center rounded-md text-muted transition hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-55"
            type="button"
            title="Copy raw message"
            aria-label="Copy raw message"
            @click="copyMessage(entry.message, true)"
          >
            <Check v-if="isCopied(entry.message, 'raw')" class="size-4" />
            <FileText v-else class="size-4" />
          </button>

          <button
            class="inline-flex size-8 items-center justify-center rounded-md text-muted transition hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-55"
            type="button"
            title="Regenerate response"
            aria-label="Regenerate response"
            :disabled="!canRegenerate(entry.message) || sending || Boolean(regeneratingMessageId)"
            @click="$emit('regenerateMessage', entry.message.id)"
          >
            <RefreshCw
              class="size-4"
              :class="
                isRegenerating(entry.message) || isActivating(entry.message) ? 'animate-spin' : ''
              "
            />
          </button>
        </div>
      </div>
    </article>

    <article
      v-if="sending"
      class="flex min-w-32 max-w-3xl flex-col gap-2 self-start rounded-lg border border-line bg-panel px-4 py-3.5 leading-6 shadow-sm"
    >
      <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span class="text-xs font-extrabold tracking-wide text-meta uppercase"> assistant </span>
      </div>
      <div class="inline-flex items-center gap-1" aria-label="Assistant is thinking">
        <span class="size-[0.45rem] animate-bounce rounded-full bg-muted" />
        <span class="size-[0.45rem] animate-bounce rounded-full bg-muted [animation-delay:120ms]" />
        <span class="size-[0.45rem] animate-bounce rounded-full bg-muted [animation-delay:240ms]" />
      </div>
    </article>
  </div>
</template>
