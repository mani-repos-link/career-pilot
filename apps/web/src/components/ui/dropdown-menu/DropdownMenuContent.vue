<script setup lang="ts">
import { DropdownMenuContent, DropdownMenuPortal, type DropdownMenuContentProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<
  DropdownMenuContentProps & {
    class?: HTMLAttributes["class"];
  }
>();
</script>

<template>
  <DropdownMenuPortal>
    <DropdownMenuContent
      v-bind="props"
      :class="
        cn(
          'z-50 min-w-36 rounded-md border border-line bg-panel p-1 text-sm text-ink shadow-lg',
          props.class,
        )
      "
    >
      <slot />
    </DropdownMenuContent>
  </DropdownMenuPortal>
</template>
