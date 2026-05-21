<script setup lang="ts">
import { ref, watch } from "vue";

const props = defineProps<{
  draftKey: string;
  sending: boolean;
}>();

const emit = defineEmits<{
  send: [content: string];
}>();

const draft = ref("");
let loadingDraft = false;

watch(
  () => props.draftKey,
  (draftKey) => {
    loadingDraft = true;
    draft.value = localStorage.getItem(draftKey) ?? "";
    loadingDraft = false;
  },
  { immediate: true },
);

watch(draft, (value) => {
  if (loadingDraft) {
    return;
  }

  const content = value.trim();
  if (content) {
    localStorage.setItem(props.draftKey, value);
  } else {
    localStorage.removeItem(props.draftKey);
  }
});

function submit() {
  const content = draft.value.trim();
  if (!content) {
    return;
  }

  emit("send", content);
  draft.value = "";
  localStorage.removeItem(props.draftKey);
}
</script>

<template>
  <form
    class="grid gap-3 border-t border-line bg-panel p-4 md:grid-cols-[minmax(0,1fr)_auto] md:px-5 md:pt-4 md:pb-5"
    @submit.prevent="submit"
  >
    <textarea
      v-model="draft"
      class="min-h-20 w-full resize-y rounded-lg border border-line-strong bg-panel px-3 py-3 text-ink outline-none transition placeholder:text-muted focus:border-brand focus:ring-[3px] focus:ring-brand-ring"
      rows="3"
      placeholder="Send a message"
      @keydown.enter.exact.prevent="submit"
    />
    <button
      class="inline-flex items-center justify-center gap-2 self-end rounded-lg border border-brand-strong bg-brand px-5 py-3 font-bold text-white transition hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-55 max-md:w-full"
      type="submit"
      :disabled="sending || !draft.trim()"
    >
      <span
        v-if="sending"
        class="size-4 animate-spin rounded-full border-2 border-white/45 border-t-white"
        aria-hidden="true"
      />
      {{ sending ? "Thinking" : "Send" }}
    </button>
  </form>
</template>
