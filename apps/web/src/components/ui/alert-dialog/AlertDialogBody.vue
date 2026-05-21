<template>
  <AlertDialogPortal>
    <AlertDialogOverlay class="fixed inset-0 z-50 bg-black/45 backdrop-blur-[1px]" />
    <AlertDialogContent
      class="fixed top-1/2 left-1/2 z-50 grid w-[min(calc(100vw-2rem),24rem)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-lg border border-line bg-panel p-5 shadow-xl"
    >
      <slot />
    </AlertDialogContent>
  </AlertDialogPortal>
</template>

<script setup lang="ts">
import { AlertDialogContent, AlertDialogOverlay, AlertDialogPortal } from "reka-ui";
</script>
