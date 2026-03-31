<template>
  <div v-if="movie" class="card">
    <div class="card__title">{{ movie.title }}</div>
    <div class="card__meta">
      <template v-if="movie.year">{{ movie.year }}</template>
    </div>
    <div style="margin-top: 16px; display: flex; gap: 12px; align-items: center">
      <span v-if="movie.source_srt_label" class="badge badge--info">
        {{ movie.source_srt_label }}
      </span>
      <span v-else class="badge badge--danger">
        {{ lang.badges.none }}
      </span>
      <span :class="movie.has_target_srt ? 'badge badge--success' : 'badge badge--warning'">
        {{ settingsStore.targetLangLabel }}: {{ movie.has_target_srt ? lang.badges.found : lang.badges.missing }}
      </span>
    </div>
    <div style="margin-top: 16px; display: flex; gap: 6px">
      <button
        v-if="!movie.has_target_srt"
        class="btn btn--icon"
        :disabled="generating"
        :title="lang.actions.generateTitle"
        @click="generate"
      >
        <span v-if="generating" class="spinner" />
        <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="6.5" cy="6.5" r="4"/>
          <line x1="9.5" y1="9.5" x2="13.5" y2="13.5"/>
        </svg>
      </button>
      <button
        v-if="movie.has_target_srt"
        class="btn btn--icon btn--icon-danger"
        :title="lang.actions.deleteTitle"
        @click="showConfirm = true"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="4" y1="4" x2="12" y2="12"/>
          <line x1="12" y1="4" x2="4" y2="12"/>
        </svg>
      </button>
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

const settingsStore = useSettingsStore();

const props = defineProps<{ id: string }>();
const movie = ref<Movie | null>(null);
const showConfirm = ref(false);
const generating = ref(false);

async function load() {
  const { data } = await moviesApi.detail(Number(props.id));
  movie.value = data;
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
  load();
});

onMounted(load);
</script>

<style scoped>
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
