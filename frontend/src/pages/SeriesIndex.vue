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
          {{ s.episode_count }} {{ s.episode_count > 1 ? lang.series.episodes : lang.series.episode }}
          <template v-if="s.first_season != null">
            &middot; {{ lang.series.season }} {{ s.first_season }}<template v-if="s.last_season !== s.first_season"> - {{ s.last_season }}</template>
          </template>
        </div>
        <div style="margin-top: 8px">
          <span
            :class="s.subtitled_count === s.episode_count ? 'badge badge--success' : 'badge badge--warning'"
          >
            {{ s.subtitled_count }}/{{ s.episode_count }} {{ lang.series.subtitled }}
          </span>
        </div>
      </router-link>
    </div>
    <div v-else class="empty-state">
      <div class="empty-state__title">{{ lang.series.empty.title }}</div>
      <div class="empty-state__text">{{ lang.series.empty.text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useLibraryStore } from "@/stores/library";
import { lang } from "@/lang";

const store = useLibraryStore();
onMounted(() => store.fetchSeries());
</script>
