<template>
  <div>
    <div v-if="loading" class="empty-state">
      <div class="empty-state__title">{{ lang.movies.loading }}</div>
    </div>
    <div v-else-if="store.movies.length" class="media-grid">
      <div v-for="m in store.movies" :key="m.id" class="card movie-card">
        <div class="card__title">{{ m.title }}</div>
        <div class="card__meta">
          <template v-if="m.year">{{ m.year }} &middot; </template>
          <span :class="m.has_target_srt ? 'badge badge--success' : 'badge badge--warning'">
            {{ m.has_target_srt ? lang.badges.subtitled : lang.badges.missing }}
          </span>
        </div>
        <button
          v-if="!m.has_target_srt"
          class="btn btn--icon movie-card__action"
          :disabled="generatingIds.has(m.id)"
          :title="lang.actions.generateTitle"
          @click="generate(m.id)"
        >
          <span v-if="generatingIds.has(m.id)" class="spinner" />
          <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="6.5" cy="6.5" r="4"/>
            <line x1="9.5" y1="9.5" x2="13.5" y2="13.5"/>
          </svg>
        </button>
        <button
          v-if="m.has_target_srt"
          class="btn btn--icon btn--icon-danger movie-card__action"
          :title="lang.actions.deleteTitle"
          @click="confirmDelete(m.id, m.title)"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="4" y1="4" x2="12" y2="12"/>
            <line x1="12" y1="4" x2="4" y2="12"/>
          </svg>
        </button>
      </div>
    </div>
    <div v-else class="empty-state">
      <div class="empty-state__title">{{ lang.movies.empty.title }}</div>
      <div class="empty-state__text">{{ lang.movies.empty.text }}</div>
    </div>
  </div>

  <ConfirmModal
    v-if="pendingDelete"
    :message="lang.confirm.deleteSubtitle(pendingDelete.title)"
    @confirm="deleteSubtitle"
    @cancel="pendingDelete = null"
  />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch, ref } from "vue";
import { useLibraryStore } from "@/stores/library";
import { useTasksStore } from "@/stores/tasks";
import { moviesApi } from "@/api";
import { lang } from "@/lang";
import ConfirmModal from "@/components/ConfirmModal.vue";

const store = useLibraryStore();
const tasksStore = useTasksStore();

const loading = ref(true);
const pendingDelete = ref<{ id: number; title: string } | null>(null);
const generatingIds = ref(new Set<number>());

async function generate(id: number) {
  generatingIds.value = new Set(generatingIds.value).add(id);
  try {
    await moviesApi.generate(id);
  } finally {
    const next = new Set(generatingIds.value);
    next.delete(id);
    generatingIds.value = next;
  }
}

function confirmDelete(id: number, title: string) {
  pendingDelete.value = { id, title };
}

async function deleteSubtitle() {
  if (!pendingDelete.value) return;
  const { id } = pendingDelete.value;
  pendingDelete.value = null;
  await moviesApi.deleteSubtitle(id);
  await store.fetchMovies();
}

watch(() => tasksStore.scanVersion, () => store.fetchMovies());

onMounted(async () => {
  await store.fetchMovies();
  loading.value = false;
  tasksStore.startScanWatcher();
});

onUnmounted(() => tasksStore.stopScanWatcher());
</script>

<style scoped>
.movie-card {
  position: relative;
}

.movie-card__action {
  position: absolute;
  bottom: 12px;
  right: 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.spinner {
  display: block;
  width: 10px;
  height: 10px;
  border: 1.5px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
</style>
