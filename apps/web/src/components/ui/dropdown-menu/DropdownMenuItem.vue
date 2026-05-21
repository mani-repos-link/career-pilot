<script setup lang="ts">
import { DropdownMenuItem, type DropdownMenuItemProps } from "reka-ui";
import type { HTMLAttributes } from "vue";
import { cn } from "@/lib/utils";

const props = defineProps<
  DropdownMenuItemProps & {
    class?: HTMLAttributes["class"];
  }
>();
</script>

<template>
  <DropdownMenuItem
    v-bind="props"
    :class="
      cn(
        'flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 outline-none hover:bg-accent focus:bg-accent',
        props.class,
      )
    "
  >
    <slot />
  </DropdownMenuItem>
</template>
