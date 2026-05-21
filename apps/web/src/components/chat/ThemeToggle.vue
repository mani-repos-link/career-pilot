<script setup lang="ts">
defineProps<{
  activeTheme: "light" | "dark";
}>();

defineEmits<{
  toggle: [];
}>();
</script>

<template>
  <button
    class="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-panel px-2.5 py-1.5 text-xs font-semibold text-ink transition hover:bg-raised focus-visible:ring-3 focus-visible:outline-none"
    type="button"
    :title="activeTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
    @click="$emit('toggle')"
  >
    <span aria-hidden="true">{{ activeTheme === "dark" ? "☾" : "☼" }}</span>
    <span>{{ activeTheme === "dark" ? "Dark" : "Light" }}</span>
  </button>
</template>
