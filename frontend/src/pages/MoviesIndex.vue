<template>
  <div>
    <div v-if="loading" class="empty-state">
      <div class="empty-state__title">{{ lang.movies.loading }}</div>
    </div>
    <div v-else-if="store.movies.length" class="media-grid">
      <router-link
        v-for="m in store.movies"
        :key="m.id"
        :to="`/movies/${m.id}`"
        class="card card--clickable card--row"
      >
        <img v-if="m.poster_url" :src="posterSrc(m.poster_url)" class="card__poster" alt="" />
        <div class="card__info">
          <div class="card__title">{{ m.title }}</div>
          <div class="card__meta">
            <template v-if="m.year">{{ m.year }} &middot; </template>
            <span :class="m.has_target_srt ? 'badge badge--success' : 'badge badge--warning'">
              {{ m.has_target_srt ? lang.badges.subtitled : lang.badges.missing }}
            </span>
          </div>
        </div>
      </router-link>
    </div>
    <div v-else class="empty-state">
      <div class="empty-state__title">{{ lang.movies.empty.title }}</div>
      <div class="empty-state__text">{{ lang.movies.empty.text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch, ref } from "vue";
import { useLibraryStore } from "@/stores/library";
import { useTasksStore } from "@/stores/tasks";
import { lang } from "@/lang";

function posterSrc(url: string): string {
  if (url.startsWith("/mediacover")) return `/api/movies/radarr-image?path=${encodeURIComponent(url)}`;
  return url;
}

const store = useLibraryStore();
const tasksStore = useTasksStore();
const loading = ref(true);

watch(() => tasksStore.scanVersion, () => store.fetchMovies());

onMounted(async () => {
  await store.fetchMovies();
  loading.value = false;
  tasksStore.startScanWatcher();
});

onUnmounted(() => tasksStore.stopScanWatcher());
</script>

<style scoped>
.card--row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
}

.card__poster {
  width: 60px;
  min-width: 60px;
  align-self: stretch;
  object-fit: cover;
  border-radius: var(--radius-sm);
  display: block;
  background: var(--bg-hover);
}

.card__info {
  flex: 1;
  min-width: 0;
}
</style>
