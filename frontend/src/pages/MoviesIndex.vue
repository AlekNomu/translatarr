<template>
  <div>
    <div v-if="store.movies.length" class="media-grid">
      <div v-for="m in store.movies" :key="m.id" class="card">
        <div class="card__title">{{ m.title }}</div>
        <div class="card__meta">
          <template v-if="m.year">{{ m.year }} &middot; </template>
          <span :class="m.has_target_srt ? 'badge badge--success' : 'badge badge--warning'">
            {{ m.has_target_srt ? "Subtitled" : "Missing" }}
          </span>
        </div>
        <div style="margin-top: 12px; display: flex; gap: 8px">
          <button
            v-if="!m.has_target_srt"
            class="btn btn--success"
            @click="generate(m.id)"
          >
            Generate Subtitles
          </button>
          <button
            v-if="m.has_target_srt"
            class="btn btn--danger"
            @click="deleteSubtitle(m.id)"
          >
            Delete Subtitle
          </button>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <div class="empty-state__title">No movies found</div>
      <div class="empty-state__text">
        Configure the movies path in Settings and run a scan.
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useLibraryStore } from "@/stores/library";
import { moviesApi } from "@/api";

const store = useLibraryStore();

async function generate(id: number) {
  await moviesApi.generate(id);
}

async function deleteSubtitle(id: number) {
  await moviesApi.deleteSubtitle(id);
  await store.fetchMovies();
}

onMounted(() => store.fetchMovies());
</script>
