<script setup lang="ts">
import ThemeToggle from "./ThemeToggle.vue";
import type { Session } from "../../types/chat";

defineProps<{
  activeTheme: "light" | "dark";
  session?: Session;
}>();

defineEmits<{
  toggleTheme: [];
}>();
</script>

<template>
  <header class="flex items-center justify-between gap-4 border-b border-line bg-header p-2 py-3">
    <div class="pl-2">
      <p class="text-xs font-bold tracking-wide text-muted uppercase">Session</p>
      <h2 class="text-xl leading-tight font-semibold text-ink">
        {{ session?.title ?? "New chat" }}
      </h2>
    </div>
    <div class="flex items-center gap-2">
      <ThemeToggle :active-theme="activeTheme" @toggle="$emit('toggleTheme')" />
    </div>
  </header>
</template>
