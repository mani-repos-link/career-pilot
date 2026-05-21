<script setup lang="ts">
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";
import { onMounted, ref, watch } from "vue";
import type { RenderRule } from "markdown-it/lib/renderer.mjs";

const props = defineProps<{
  collapsed: boolean;
  content: string;
}>();

const renderedHtml = ref("");

const markdown = new MarkdownIt({
  breaks: true,
  html: false,
  linkify: true,
  typographer: true,
});

const defaultFenceRenderer = markdown.renderer.rules.fence;
const proseFenceRenderer: RenderRule = (tokens, index, options, env, self) => {
  const token = tokens[index];
  if (!isUnlabeledProseFence(token.info, token.content)) {
    return (
      defaultFenceRenderer?.(tokens, index, options, env, self) ??
      self.renderToken(tokens, index, options)
    );
  }

  return `<div class="my-3 w-full rounded-md border border-line bg-raised p-3 whitespace-pre-wrap break-words text-ink [overflow-wrap:anywhere]">${markdown.utils.escapeHtml(token.content.trim())}</div>\n`;
};

markdown.renderer.rules.fence = proseFenceRenderer;

function isUnlabeledProseFence(info: string, content: string) {
  const hasLanguage = info.trim().length > 0;
  const text = content.trim();
  if (hasLanguage || !text) {
    return false;
  }

  const wordCount = text.match(/[A-Za-z]{3,}/g)?.length ?? 0;
  const hasSentencePunctuation = /[.!?]["')\]]?(\s|$)/.test(text);
  const looksLikeCode =
    /[{};=<>]|^\s*(class|const|def|export|for|function|if|import|let|select|while)\b/im.test(text);

  return !looksLikeCode && (wordCount >= 12 || hasSentencePunctuation);
}

function renderMarkdown() {
  const rawHtml = markdown.render(props.content);
  renderedHtml.value = sanitizeHtml(rawHtml);
}

function sanitizeHtml(html: string) {
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ["class", "style"],
  });
}

onMounted(renderMarkdown);
watch(() => props.content, renderMarkdown);
</script>

<template>
  <div
    class="relative block w-full min-w-0 max-w-full overflow-x-auto break-words text-ink [overflow-wrap:anywhere] [&_*:first-child]:mt-0 [&_*:last-child]:mb-0 [&_a]:font-semibold [&_a]:text-brand [&_a]:underline [&_blockquote]:border-l-4 [&_blockquote]:border-line-strong [&_blockquote]:pl-3 [&_code]:max-w-full [&_code]:break-words [&_code]:rounded [&_code]:bg-raised [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.9em] [&_h1]:mt-4 [&_h1]:mb-2 [&_h1]:max-w-full [&_h1]:break-words [&_h1]:text-xl [&_h1]:font-bold [&_h2]:mt-4 [&_h2]:mb-2 [&_h2]:max-w-full [&_h2]:break-words [&_h2]:text-lg [&_h2]:font-bold [&_h3]:mt-3 [&_h3]:mb-1.5 [&_h3]:max-w-full [&_h3]:break-words [&_h3]:font-bold [&_li]:my-1 [&_li]:max-w-full [&_li]:break-words [&_ol]:my-2 [&_ol]:max-w-full [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_p]:max-w-full [&_p]:break-words [&_pre]:my-3 [&_pre]:w-full [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_pre]:whitespace-pre [&_pre]:rounded-md [&_pre]:border [&_pre]:border-line [&_pre]:p-3 [&_pre_code]:whitespace-pre [&_pre_code]:break-normal [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_table]:my-3 [&_table]:block [&_table]:w-full [&_table]:max-w-full [&_table]:overflow-x-auto [&_table]:border-collapse [&_td]:border [&_td]:border-line [&_td]:p-2 [&_td]:break-words [&_td]:[overflow-wrap:anywhere] [&_th]:border [&_th]:border-line [&_th]:bg-raised [&_th]:p-2 [&_th]:break-words [&_th]:[overflow-wrap:anywhere] [&_ul]:my-2 [&_ul]:max-w-full [&_ul]:list-disc [&_ul]:pl-5"
    :class="
      collapsed
        ? 'max-h-80 overflow-y-hidden after:pointer-events-none after:absolute after:inset-x-0 after:bottom-0 after:h-12 after:bg-linear-to-b after:from-transparent after:to-panel'
        : ''
    "
    v-html="renderedHtml"
  />
</template>
