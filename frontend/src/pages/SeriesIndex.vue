<template>
  <div>
    <div v-if="loading" class="empty-state">
      <div class="empty-state__title">{{ lang.series.loading }}</div>
    </div>
    <template v-else-if="store.series.length">
      <div class="media-grid">
        <router-link
          v-for="s in paginated"
          :key="s.series_name"
          :to="`/series/${encodeURIComponent(s.series_name)}`"
          class="card card--clickable card--row"
        >
          <img v-if="s.poster_url" :src="s.poster_url" class="card__poster" alt="" />
          <div class="card__info">
            <div class="card__title">{{ s.series_name }}</div>
            <div class="card__meta">
              {{ s.episode_count }} {{ s.episode_count > 1 ? lang.series.episodes : lang.series.episode }}
              <template v-if="s.first_season != null">
                &middot; {{ lang.series.season }} {{ s.first_season }}<template v-if="s.last_season !== s.first_season"> - {{ s.last_season }}</template>
              </template>
            </div>
            <div style="margin-top: 8px">
              <span :class="s.subtitled_count === s.episode_count ? 'badge badge--success' : 'badge badge--warning'">
                {{ s.subtitled_count }}/{{ s.episode_count }} {{ lang.series.subtitled }}
              </span>
            </div>
          </div>
        </router-link>
      </div>
      <div v-if="totalPages > 1" class="pagination">
        <button class="btn btn--secondary" :disabled="page === 1" @click="page--">{{ lang.series.prev }}</button>
        <span class="pagination__info">{{ lang.series.page(page, totalPages) }}</span>
        <button class="btn btn--secondary" :disabled="page === totalPages" @click="page++">{{ lang.series.next }}</button>
      </div>
    </template>
    <div v-else class="empty-state">
      <div class="empty-state__title">{{ lang.series.empty.title }}</div>
      <div class="empty-state__text">{{ lang.series.empty.text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, computed } from "vue";
import { useLibraryStore } from "@/stores/library";
import { useTasksStore } from "@/stores/tasks";
import { lang } from "@/lang";

const PAGE_SIZE = 50;

const store = useLibraryStore();
const tasksStore = useTasksStore();
const loading = ref(true);
const page = ref(1);

const totalPages = computed(() => Math.ceil(store.series.length / PAGE_SIZE));
const paginated = computed(() => store.series.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE));

watch(() => tasksStore.scanVersion, () => { store.fetchSeries(); page.value = 1; });

onMounted(async () => {
  await store.fetchSeries();
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

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
}

.pagination__info {
  color: var(--text-muted);
  font-size: 0.875rem;
}
</style>
