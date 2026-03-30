<template>
  <div v-if="movie" class="card">
    <div class="card__title">{{ movie.title }}</div>
    <div class="card__meta">
      <template v-if="movie.year">{{ movie.year }}</template>
    </div>
    <div style="margin-top: 16px; display: flex; gap: 12px; align-items: center">
      <span :class="movie.has_source_srt ? 'badge badge--success' : 'badge badge--danger'">
        Source SRT: {{ movie.has_source_srt ? "Found" : "None" }}
      </span>
      <span :class="movie.has_target_srt ? 'badge badge--success' : 'badge badge--warning'">
        Target SRT: {{ movie.has_target_srt ? "Found" : "Missing" }}
      </span>
    </div>
    <div style="margin-top: 16px; display: flex; gap: 8px">
      <button v-if="!movie.has_target_srt" class="btn btn--success" @click="generate">
        Generate Subtitles
      </button>
      <button v-if="movie.has_target_srt" class="btn btn--danger" @click="deleteSubtitle">
        Delete Subtitle
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { moviesApi } from "@/api";
import type { Movie } from "@/stores/library";

const props = defineProps<{ id: string }>();
const movie = ref<Movie | null>(null);

async function load() {
  const { data } = await moviesApi.detail(Number(props.id));
  movie.value = data;
}

async function generate() {
  await moviesApi.generate(Number(props.id));
}

async function deleteSubtitle() {
  await moviesApi.deleteSubtitle(Number(props.id));
  await load();
}

onMounted(load);
</script>
