<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import ChatComposer from "./components/chat/ChatComposer.vue";
import ChatHeader from "./components/chat/ChatHeader.vue";
import ChatSidebar from "./components/chat/ChatSidebar.vue";
import MessageList from "./components/chat/MessageList.vue";
import { useChat } from "./composables/useChat";
import { useTheme } from "./composables/useTheme";

const chat = useChat();
const theme = useTheme();
const sidebarCollapsed = ref(false);

onMounted(() => {
  sidebarCollapsed.value = localStorage.getItem("careerpilot.sidebar.collapsed") === "true";
});

watch(sidebarCollapsed, (collapsed) => {
  localStorage.setItem("careerpilot.sidebar.collapsed", String(collapsed));
});
</script>

<template>
  <main
    class="grid min-h-svh bg-shell text-ink md:h-svh md:overflow-hidden"
    :class="
      sidebarCollapsed ? 'md:grid-cols-[64px_minmax(0,1fr)]' : 'md:grid-cols-[300px_minmax(0,1fr)]'
    "
  >
    <ChatSidebar
      :collapsed="sidebarCollapsed"
      :loading="chat.loading.value"
      :selected-session-id="chat.selectedSessionId.value"
      :sessions="chat.sessions.value"
      @delete-session="chat.deleteSession"
      @new-session="chat.newSession"
      @rename-session="chat.renameSession"
      @select-session="chat.selectSession"
      @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
    />

    <section
      class="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)_auto_auto] overflow-hidden"
      aria-label="Active chat"
    >
      <ChatHeader
        :active-theme="theme.appliedTheme.value"
        :session="chat.activeSession.value"
        @toggle-theme="theme.toggleTheme"
      />
      <MessageList
        :activating-message-id="chat.activatingMessageId.value"
        :has-older-messages="chat.messagesHasMore.value"
        :loading-older-messages="chat.loadingOlderMessages.value"
        :messages="chat.messages.value"
        :regenerating-message-id="chat.regeneratingMessageId.value"
        :sending="chat.sending.value"
        :session-id="chat.selectedSessionId.value"
        @activate-message="chat.activateMessage"
        @load-older-messages="chat.loadOlderMessages"
        @regenerate-message="chat.regenerateMessage"
      />

      <p
        v-if="chat.error.value"
        class="mx-4 mb-3 rounded-lg border border-danger-300 bg-danger-50 px-3 py-2.5 text-sm text-danger-700 md:mx-6"
      >
        {{ chat.error.value }}
      </p>

      <ChatComposer
        :draft-key="chat.draftKey.value"
        :sending="chat.sending.value"
        @send="chat.sendMessage"
      />
    </section>
  </main>
</template>
