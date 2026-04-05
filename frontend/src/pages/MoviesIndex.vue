<template>
  <div>
    <div v-if="loading" class="empty-state">
      <div class="empty-state__title">{{ lang.movies.loading }}</div>
    </div>
    <template v-else-if="store.movies.length">
      <div class="media-grid">
        <router-link
          v-for="m in paginated"
          :key="m.id"
          :to="`/movies/${m.id}`"
          class="card card--clickable card--row"
        >
          <img v-if="m.poster_url" :src="m.poster_url" class="card__poster" alt="" />
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
      <div v-if="totalPages > 1" class="pagination">
        <button class="btn btn--secondary" :disabled="page === 1" @click="page--">{{ lang.movies.prev }}</button>
        <span class="pagination__info">{{ lang.movies.page(page, totalPages) }}</span>
        <button class="btn btn--secondary" :disabled="page === totalPages" @click="page++">{{ lang.movies.next }}</button>
      </div>
    </template>
    <div v-else class="empty-state">
      <div class="empty-state__title">{{ lang.movies.empty.title }}</div>
      <div class="empty-state__text">{{ lang.movies.empty.text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch, ref, computed } from "vue";
import { useLibraryStore } from "@/stores/library";
import { useTasksStore } from "@/stores/tasks";
import { lang } from "@/lang";

const PAGE_SIZE = 50;

const store = useLibraryStore();
const tasksStore = useTasksStore();
const loading = ref(true);
const page = ref(1);

const totalPages = computed(() => Math.ceil(store.movies.length / PAGE_SIZE));
const paginated = computed(() => store.movies.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE));

watch(() => tasksStore.scanVersion, () => { store.fetchMovies(); page.value = 1; });

onMounted(async () => {
  await store.fetchMovies();
  loading.value = false;
  tasksStore.startScanWatcher();
});

onUnmounted(() => tasksStore.stopScanWatcher());
</script>

<style scoped>
.pagination {
  gap: 16px;
  margin-top: 24px;
}

.pagination__info {
  color: var(--text-muted);
  font-size: 0.875rem;
}
</style>
