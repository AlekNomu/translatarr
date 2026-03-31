<template>
  <div>
    <div class="series-header">
      <h2>{{ name }}</h2>
      <div style="display: flex; gap: 8px">
        <button class="btn btn--primary" :disabled="generatingAll" @click="generateAll">
          {{ generatingAll ? lang.series.queuing : lang.series.generateAllMissing }}
        </button>
        <button
          v-if="hasAnySubtitle"
          class="btn btn--danger"
          :disabled="deletingAll"
          @click="deleteAll"
        >
          {{ deletingAll ? lang.series.deleting : lang.series.deleteAllSubtitles }}
        </button>
      </div>
    </div>

    <div v-if="seasons.length === 0" class="empty-state">
      <div class="empty-state__title">{{ lang.series.noEpisodes }}</div>
    </div>

    <div v-for="season in seasons" :key="season.number" class="season">
      <div class="season__header">
        <span class="season__title">{{ lang.series.season }} {{ pad(season.number) }}</span>
        <span class="season__meta">
          {{ season.subtitled }} / {{ season.episodes.length }} {{ lang.series.subtitled }}
        </span>
        <button
          class="btn btn--primary"
          :disabled="generatingSeasons.has(season.number) || season.missing === 0"
          @click="generateSeason(season.number)"
        >
          {{ generatingSeasons.has(season.number) ? lang.series.queuing : lang.series.generateSeason }}
        </button>
        <button
          v-if="season.subtitled > 0"
          class="btn btn--danger"
          :disabled="deletingSeasons.has(season.number)"
          @click="deleteSeason(season.number)"
        >
          {{ deletingSeasons.has(season.number) ? lang.series.deleting : lang.series.deleteSeasonSubtitles }}
        </button>
      </div>

      <table class="table">
        <thead>
          <tr>
            <th>{{ lang.series.table.episode }}</th>
            <th>{{ lang.series.table.title }}</th>
            <th>{{ lang.series.table.sourceSrt }}</th>
            <th>{{ lang.series.table.targetSrt }}</th>
            <th>{{ lang.series.table.actions }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="ep in season.episodes" :key="ep.id">
            <td>S{{ pad(ep.season) }}E{{ pad(ep.episode) }}</td>
            <td>{{ ep.title }}</td>
            <td>
              <span :class="ep.has_source_srt ? 'badge badge--success' : 'badge badge--danger'">
                {{ ep.has_source_srt ? lang.badges.yes : lang.badges.no }}
              </span>
            </td>
            <td>
              <span :class="ep.has_target_srt ? 'badge badge--success' : 'badge badge--warning'">
                {{ ep.has_target_srt ? lang.badges.yes : lang.badges.missing }}
              </span>
            </td>
            <td style="display: flex; gap: 6px">
              <button
                v-if="!ep.has_target_srt"
                class="btn btn--success"
                @click="generateEpisode(ep.id)"
              >
                {{ lang.actions.generate }}
              </button>
              <button
                v-if="ep.has_target_srt"
                class="btn btn--danger"
                @click="deleteEpisode(ep.id)"
              >
                {{ lang.actions.delete }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { seriesApi } from "@/api";
import type { Episode } from "@/stores/library";
import { lang } from "@/lang";

interface SeasonGroup {
  number: number;
  episodes: Episode[];
  subtitled: number;
  missing: number;
}

const props = defineProps<{ name: string }>();
const episodes = ref<Episode[]>([]);
const generatingAll = ref(false);
const generatingSeasons = ref(new Set<number>());
const deletingAll = ref(false);
const deletingSeasons = ref(new Set<number>());

const seasons = computed<SeasonGroup[]>(() => {
  const map = new Map<number, Episode[]>();
  for (const ep of episodes.value) {
    const s = ep.season ?? 0;
    if (!map.has(s)) map.set(s, []);
    map.get(s)!.push(ep);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a - b)
    .map(([number, eps]) => ({
      number,
      episodes: eps,
      subtitled: eps.filter(e => e.has_target_srt).length,
      missing: eps.filter(e => !e.has_target_srt).length,
    }));
});

const hasAnySubtitle = computed(() => episodes.value.some(e => e.has_target_srt));

function pad(n: number | null): string {
  return n != null ? String(n).padStart(2, "0") : "??";
}

async function load() {
  const { data } = await seriesApi.detail(props.name);
  episodes.value = data.episodes;
}

async function generateAll() {
  generatingAll.value = true;
  try {
    await seriesApi.generate(props.name);
  } finally {
    generatingAll.value = false;
  }
}

async function generateSeason(seasonNumber: number) {
  generatingSeasons.value = new Set(generatingSeasons.value).add(seasonNumber);
  try {
    await seriesApi.generateSeason(props.name, seasonNumber);
  } finally {
    const next = new Set(generatingSeasons.value);
    next.delete(seasonNumber);
    generatingSeasons.value = next;
  }
}

async function generateEpisode(id: number) {
  await seriesApi.generateEpisode(props.name, id);
}

async function deleteAll() {
  deletingAll.value = true;
  try {
    await seriesApi.deleteSubtitle(props.name);
    await load();
  } finally {
    deletingAll.value = false;
  }
}

async function deleteSeason(seasonNumber: number) {
  deletingSeasons.value = new Set(deletingSeasons.value).add(seasonNumber);
  try {
    await seriesApi.deleteSeasonSubtitle(props.name, seasonNumber);
    await load();
  } finally {
    const next = new Set(deletingSeasons.value);
    next.delete(seasonNumber);
    deletingSeasons.value = next;
  }
}

async function deleteEpisode(id: number) {
  await seriesApi.deleteEpisodeSubtitle(props.name, id);
  await load();
}

onMounted(load);
</script>

<style scoped>
.series-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.season {
  margin-bottom: 28px;
}

.season__header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
}

.season__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.season__meta {
  font-size: 13px;
  color: var(--text-muted);
  flex: 1;
}
</style>
