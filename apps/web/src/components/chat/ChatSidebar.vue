<script setup lang="ts">
import {
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  Trash2,
} from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import type { Session } from "../../types/chat";
import { formatTime } from "../../utils/date";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogBody,
  AlertDialogCancel,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const props = defineProps<{
  collapsed: boolean;
  loading: boolean;
  selectedSessionId: string | null;
  sessions: Session[];
}>();

const emit = defineEmits<{
  deleteSession: [sessionId: string];
  newSession: [];
  renameSession: [sessionId: string, title: string];
  selectSession: [sessionId: string];
  toggleCollapse: [];
}>();

const deleteDialogOpen = ref(false);
const deleteTarget = ref<Session | null>(null);
const renameDialogOpen = ref(false);
const renameTarget = ref<Session | null>(null);
const renameTitle = ref("");
const visibleSessionCount = ref(60);

const visibleSessions = computed(() => props.sessions.slice(0, visibleSessionCount.value));
const hasMoreSessions = computed(() => visibleSessionCount.value < props.sessions.length);

watch(
  () => props.sessions.length,
  () => {
    visibleSessionCount.value = Math.min(
      Math.max(visibleSessionCount.value, 60),
      props.sessions.length || 60,
    );
  },
);

function requestDelete(session: Session) {
  deleteTarget.value = session;
  deleteDialogOpen.value = true;
}

function requestRename(session: Session) {
  renameTarget.value = session;
  renameTitle.value = session.title;
  renameDialogOpen.value = true;
}

function confirmDelete() {
  if (!deleteTarget.value) {
    return;
  }

  emit("deleteSession", deleteTarget.value.id);
  deleteDialogOpen.value = false;
  deleteTarget.value = null;
}

function confirmRename() {
  const title = renameTitle.value.trim();
  if (!renameTarget.value || !title) {
    return;
  }

  emit("renameSession", renameTarget.value.id, title);
  renameDialogOpen.value = false;
  renameTarget.value = null;
  renameTitle.value = "";
}

function loadMoreSessions() {
  visibleSessionCount.value = Math.min(visibleSessionCount.value + 40, props.sessions.length);
}

function handleSessionScroll(event: Event) {
  if (!hasMoreSessions.value) {
    return;
  }

  const element = event.currentTarget;
  if (!(element instanceof HTMLElement)) {
    return;
  }

  const nearVerticalEnd = element.scrollTop + element.clientHeight >= element.scrollHeight - 96;
  const nearHorizontalEnd = element.scrollLeft + element.clientWidth >= element.scrollWidth - 96;

  if (nearVerticalEnd || nearHorizontalEnd) {
    loadMoreSessions();
  }
}
</script>

<template>
  <aside
    class="flex min-h-0 flex-col border-b border-line bg-panel transition-[width] md:min-h-svh md:border-r md:border-b-0"
    :class="collapsed ? 'md:w-16' : 'md:w-full'"
  >
    <div
      class="flex items-center border-b border-line p-2 py-4"
      :class="collapsed ? 'justify-center md:flex-col md:gap-2 md:px-2' : 'justify-between gap-4'"
    >
      <div v-if="!collapsed" class="px-2">
        <h1 class="text-2xl leading-tight font-semibold text-ink">Career Pilot</h1>
      </div>
      <div class="flex items-center gap-1" :class="collapsed ? 'flex-col' : ''">
        <Button
          size="icon"
          :title="collapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          :aria-label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          variant="ghost"
          @click="$emit('toggleCollapse')"
        >
          <PanelLeftOpen v-if="collapsed" />
          <PanelLeftClose v-else />
        </Button>
        <Button size="icon" title="New chat" aria-label="New chat" @click="$emit('newSession')">
          <Plus />
        </Button>
      </div>
    </div>

    <div
      v-if="!collapsed"
      class="flex gap-2 overflow-x-auto p-2 md:min-h-0 md:flex-1 md:flex-col md:overflow-x-hidden md:overflow-y-auto"
      aria-label="Chat sessions"
      @scroll="handleSessionScroll"
    >
      <div
        v-for="session in visibleSessions"
        :key="session.id"
        class="grid min-h-11 min-w-52 grid-cols-[minmax(0,1fr)_auto] items-center rounded-md border transition md:w-full md:min-w-0"
        :class="
          session.id === selectedSessionId
            ? 'border-line-strong bg-raised'
            : 'border-transparent hover:border-line-strong hover:bg-subtle'
        "
      >
        <button
          class="min-w-0 bg-transparent px-2.5 py-2 text-left"
          type="button"
          @click="$emit('selectSession', session.id)"
        >
          <span class="block w-full truncate text-sm font-semibold text-ink">
            {{ session.title }}
          </span>
          <small class="text-xs text-muted">
            {{ formatTime(session.updatedAt) }}
          </small>
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <Button
              class="mr-1 text-muted hover:bg-raised hover:text-ink"
              variant="ghost"
              size="icon"
              :aria-label="`Open actions for ${session.title}`"
              title="Conversation actions"
              @click.stop
            >
              <MoreHorizontal />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem @select="requestRename(session)">
              <Pencil />
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem class="text-destructive" @select="requestDelete(session)">
              <Trash2 />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <button
        v-if="hasMoreSessions"
        class="min-h-9 min-w-28 rounded-md border border-line bg-panel px-3 py-2 text-[0.8125rem] font-semibold text-muted hover:bg-raised hover:text-ink"
        type="button"
        @click="loadMoreSessions"
      >
        Load more
      </button>

      <p v-if="!loading && sessions.length === 0" class="px-3 py-4 text-sm text-muted">
        No sessions yet.
      </p>
    </div>

    <AlertDialog v-model:open="deleteDialogOpen">
      <AlertDialogBody>
        <AlertDialogHeader>
          <AlertDialogTitle class="text-lg font-semibold text-ink">
            Delete conversation?
          </AlertDialogTitle>
          <AlertDialogDescription class="text-sm leading-6 text-muted">
            This removes "{{ deleteTarget?.title }}" from your local history.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel as-child>
            <Button variant="outline" size="sm">Cancel</Button>
          </AlertDialogCancel>
          <AlertDialogAction as-child>
            <Button variant="destructive" size="sm" @click="confirmDelete">Delete</Button>
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogBody>
    </AlertDialog>

    <AlertDialog v-model:open="renameDialogOpen">
      <AlertDialogBody>
        <AlertDialogHeader>
          <AlertDialogTitle class="text-lg font-semibold text-ink">Rename chat</AlertDialogTitle>
          <AlertDialogDescription class="text-sm leading-6 text-muted">
            Choose a name for this conversation.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <input
          v-model="renameTitle"
          class="h-10 w-full rounded-md border border-line bg-raised px-3 text-sm text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          maxlength="120"
          placeholder="Chat title"
          type="text"
          @keydown.enter.prevent="confirmRename"
        />
        <AlertDialogFooter>
          <AlertDialogCancel as-child>
            <Button variant="outline" size="sm">Cancel</Button>
          </AlertDialogCancel>
          <AlertDialogAction as-child>
            <Button size="sm" :disabled="!renameTitle.trim()" @click="confirmRename">Rename</Button>
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogBody>
    </AlertDialog>
  </aside>
</template>
