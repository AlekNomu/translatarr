<template>
  <div v-if="movie">
    <div class="movie-header">
      <h2 v-if="!metadata">{{ movie.title }}</h2>
      <div class="movie-header__actions">
        <button
          v-if="!movie.has_target_srt"
          class="btn btn--labeled"
          :disabled="generating"
          @click="generate"
        >
          <span v-if="generating" class="spinner" />
          <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="6.5" cy="6.5" r="4"/>
            <line x1="9.5" y1="9.5" x2="13.5" y2="13.5"/>
          </svg>
          {{ generating ? lang.series.queuing : lang.actions.generateSubtitles }}
        </button>
        <button
          v-if="movie.has_target_srt"
          class="btn btn--labeled btn--labeled-danger"
          @click="showConfirm = true"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="4" y1="4" x2="12" y2="12"/>
            <line x1="12" y1="4" x2="4" y2="12"/>
          </svg>
          {{ lang.actions.deleteSubtitle }}
        </button>
      </div>
    </div>

    <div v-if="metadata" class="movie-meta">
      <img
        v-if="metadata.poster_url"
        :src="posterSrc(metadata.poster_url)"
        class="movie-meta__poster"
        alt=""
      />
      <div class="movie-meta__body">
        <h2 class="movie-meta__title">{{ movie.title }}</h2>
        <div class="movie-chips">
          <span v-if="movie.year" class="chip">🎬 {{ movie.year }}</span>
          <span v-if="metadata.movie_path" class="chip">📁 {{ metadata.movie_path }}</span>
          <span v-if="movie.source_srt_label" class="chip">🎙 {{ movie.source_srt_label }}</span>
          <span class="chip" :class="movie.has_target_srt ? 'chip--success' : 'chip--warning'">
            {{ movie.has_target_srt ? '✅' : '⚠️' }} {{ settingsStore.targetLangLabel }}: {{ movie.has_target_srt ? lang.badges.found : lang.badges.missing }}
          </span>
        </div>
        <p v-if="metadata.overview" class="movie-meta__overview">{{ metadata.overview }}</p>
      </div>
    </div>

    <div v-if="!metadata" style="margin-top: 16px; display: flex; gap: 12px; align-items: center">
      <span v-if="movie.source_srt_label" class="badge badge--info">{{ movie.source_srt_label }}</span>
      <span v-else class="badge badge--danger">{{ lang.badges.none }}</span>
      <span :class="movie.has_target_srt ? 'badge badge--success' : 'badge badge--warning'">
        {{ settingsStore.targetLangLabel }}: {{ movie.has_target_srt ? lang.badges.found : lang.badges.missing }}
      </span>
    </div>
  </div>

  <ConfirmModal
    v-if="showConfirm && movie"
    :message="lang.confirm.deleteSubtitle(movie.title)"
    @confirm="deleteSubtitle"
    @cancel="showConfirm = false"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { moviesApi } from "@/api";
import type { Movie } from "@/stores/library";
import { lang } from "@/lang";
import { useSettingsStore } from "@/stores/settings";
import ConfirmModal from "@/components/ConfirmModal.vue";

interface MovieMetadata {
  poster_url: string | null;
  overview: string | null;
  movie_path: string | null;
}

const settingsStore = useSettingsStore();

const props = defineProps<{ id: string }>();
const movie = ref<Movie | null>(null);
const metadata = ref<MovieMetadata | null>(null);
const showConfirm = ref(false);
const generating = ref(false);

function posterSrc(url: string): string {
  if (url.startsWith("/mediacover")) return `/api/movies/radarr-image?path=${encodeURIComponent(url)}`;
  return url;
}

async function load() {
  const { data } = await moviesApi.detail(Number(props.id));
  movie.value = data;
  metadata.value = data.metadata ?? null;
}

async function generate() {
  generating.value = true;
  try {
    await moviesApi.generate(Number(props.id));
  } finally {
    generating.value = false;
  }
}

async function deleteSubtitle() {
  showConfirm.value = false;
  await moviesApi.deleteSubtitle(Number(props.id));
  await load();
}

watch(() => props.id, () => {
  movie.value = null;
  metadata.value = null;
  load();
});

onMounted(load);
</script>

<style scoped>
.movie-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.movie-header__actions {
  display: flex;
  gap: 8px;
}

.btn--labeled {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  height: 34px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font);
  cursor: pointer;
  transition: all 0.15s;

  svg { width: 14px; height: 14px; flex-shrink: 0; }

  &:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--border-light);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn--labeled-danger:hover {
  color: var(--danger);
  border-color: var(--danger);
  background: rgba(218, 54, 51, 0.08);
}

.movie-meta {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
  align-items: flex-start;
}

.movie-meta__poster {
  width: 120px;
  min-width: 120px;
  border-radius: var(--radius);
  object-fit: cover;
  aspect-ratio: 2/3;
  background: var(--bg-hover);
  display: block;
}

.movie-meta__body {
  flex: 1;
  min-width: 0;
}

.movie-meta__title {
  margin: 0 0 10px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.movie-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.chip {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}

.chip--success { border-color: var(--success); color: var(--success-light); }
.chip--warning { border-color: var(--warning); color: var(--warning); }

.movie-meta__overview {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
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
