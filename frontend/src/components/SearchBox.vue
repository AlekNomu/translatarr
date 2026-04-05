<template>
  <div class="search-box" ref="boxEl">
    <span class="search-box__icon">&#x1F50D;</span>
    <input
      class="search-input"
      v-model="query"
      @keydown.escape="close"
      :placeholder="lang.header.searchPlaceholder"
    />
    <div v-if="query" class="search-dropdown">
      <div v-if="seriesResults.length">
        <div class="search-dropdown__label">{{ lang.nav.series }}</div>
        <div
          v-for="s in seriesResults"
          :key="s.series_name"
          class="search-dropdown__item"
          @mousedown.prevent="goSeries(s)"
        >
          <div class="search-dropdown__thumb">
            <img v-if="s.poster_url" :src="s.poster_url" alt="" />
          </div>
          <div class="search-dropdown__info">
            <div class="search-dropdown__name">{{ s.series_name }}</div>
            <div class="search-dropdown__meta">
              {{ s.episode_count }} {{ s.episode_count > 1 ? lang.series.episodes : lang.series.episode }}
            </div>
          </div>
        </div>
      </div>
      <div v-if="movieResults.length">
        <div class="search-dropdown__label">{{ lang.nav.movies }}</div>
        <div
          v-for="m in movieResults"
          :key="m.id"
          class="search-dropdown__item"
          @mousedown.prevent="goMovie(m)"
        >
          <div class="search-dropdown__thumb">
            <img v-if="m.poster_url" :src="m.poster_url" alt="" />
          </div>
          <div class="search-dropdown__info">
            <div class="search-dropdown__name">{{ m.title }}</div>
            <div v-if="m.year" class="search-dropdown__meta">{{ m.year }}</div>
          </div>
        </div>
      </div>
      <div
        v-if="!seriesResults.length && !movieResults.length"
        class="search-dropdown__empty"
      >
        {{ lang.header.noResults }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useLibraryStore } from "@/stores/library";
import type { SeriesSummary, Movie } from "@/stores/library";
import { lang } from "@/lang";

const router = useRouter();
const store = useLibraryStore();
const query = ref("");
const boxEl = ref<HTMLElement | null>(null);

const seriesResults = computed(() => {
  const q = query.value.toLowerCase();
  if (!q) return [];
  return store.series.filter(s => s.series_name.toLowerCase().includes(q)).slice(0, 5);
});

const movieResults = computed(() => {
  const q = query.value.toLowerCase();
  if (!q) return [];
  return store.movies.filter(m => m.title.toLowerCase().includes(q)).slice(0, 5);
});

function close() {
  query.value = "";
}

function goSeries(s: SeriesSummary) {
  router.push(`/series/${encodeURIComponent(s.series_name)}`);
  close();
}

function goMovie(m: Movie) {
  router.push(`/movies/${m.id}`);
  close();
}

function onOutside(e: MouseEvent) {
  if (boxEl.value && !boxEl.value.contains(e.target as Node)) {
    close();
  }
}

function onInput() {
  if (!store.series.length) store.fetchSeries();
  if (!store.movies.length) store.fetchMovies();
}

let inputEl: HTMLInputElement | null = null;

onMounted(() => {
  document.addEventListener("mousedown", onOutside);
  inputEl = boxEl.value?.querySelector("input") ?? null;
  if (inputEl) inputEl.addEventListener("input", onInput);
});

onUnmounted(() => {
  document.removeEventListener("mousedown", onOutside);
  if (inputEl) inputEl.removeEventListener("input", onInput);
});
</script>
