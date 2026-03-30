<template>
  <div>
    <div v-if="store.series.length" class="media-grid">
      <router-link
        v-for="s in store.series"
        :key="s.series_name"
        :to="`/series/${encodeURIComponent(s.series_name)}`"
        class="card card--clickable"
      >
        <div class="card__title">{{ s.series_name }}</div>
        <div class="card__meta">
          {{ s.episode_count }} episode{{ s.episode_count > 1 ? "s" : "" }}
          <template v-if="s.first_season != null">
            &middot; Season {{ s.first_season }}<template v-if="s.last_season !== s.first_season"> - {{ s.last_season }}</template>
          </template>
        </div>
        <div style="margin-top: 8px">
          <span
            :class="s.subtitled_count === s.episode_count ? 'badge badge--success' : 'badge badge--warning'"
          >
            {{ s.subtitled_count }}/{{ s.episode_count }} subtitled
          </span>
        </div>
      </router-link>
    </div>
    <div v-else class="empty-state">
      <div class="empty-state__title">No series found</div>
      <div class="empty-state__text">
        Configure the series path in Settings and run a scan.
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useLibraryStore } from "@/stores/library";

const store = useLibraryStore();
onMounted(() => store.fetchSeries());
</script>
