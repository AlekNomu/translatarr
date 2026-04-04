<template>
  <div>
    <div v-if="!metadata" class="series-header">
      <h2>{{ name }}</h2>
    </div>

    <div v-if="metadata" class="series-meta">
      <img
        v-if="metadata.poster_url"
        :src="metadata.poster_url"
        class="series-meta__poster"
        alt=""
      />
      <div class="series-meta__body">
        <h2 class="series-meta__title">{{ name }}</h2>
        <div class="series-chips">
          <span v-if="metadata.series_path" class="chip">📁 {{ metadata.series_path }}</span>
          <span class="chip">📺 {{ episodes.length }} {{ episodes.length > 1 ? lang.series.episodes : lang.series.episode }}</span>
          <span class="chip" :class="missingCount === 0 ? 'chip--success' : 'chip--warning'">
            {{ missingCount === 0 ? '✅' : '⚠️' }} {{ missingCount }} missing
          </span>
          <span v-if="metadata.status" class="chip" :class="metadata.status === 'ended' ? 'chip--muted' : 'chip--success'">
            {{ statusLabel(metadata.status) }}
          </span>
          <span v-if="metadata.last_aired" class="chip">📅 {{ formatDate(metadata.last_aired) }}</span>
        </div>
        <p v-if="metadata.overview" class="series-meta__overview">{{ metadata.overview }}</p>
      </div>
    </div>

    <div v-if="seasons.length === 0" class="empty-state">
      <div class="empty-state__title">{{ lang.series.noEpisodes }}</div>
    </div>

    <div v-if="seasons.length > 0" class="seasons-actions">
      <button
        class="btn btn--icon"
        :disabled="generatingAll"
        :title="generatingAll ? lang.series.queuing : lang.series.generateAllMissing"
        @click="generateAll"
      >
        <span v-if="generatingAll" class="spinner" />
        <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="6.5" cy="6.5" r="4"/>
          <line x1="9.5" y1="9.5" x2="13.5" y2="13.5"/>
        </svg>
      </button>
      <button
        v-if="hasAnySubtitle"
        class="btn btn--icon btn--icon-danger"
        :disabled="deletingAll"
        :title="lang.series.deleteAllSubtitles"
        @click="pendingDelete = { type: 'series' }"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="4" y1="4" x2="12" y2="12"/>
          <line x1="12" y1="4" x2="4" y2="12"/>
        </svg>
      </button>
    </div>

    <div v-for="season in seasons" :key="season.number" class="season">
      <div class="season__header" @click="toggleSeason(season.number)">
        <svg
          class="season__chevron"
          :class="{ 'season__chevron--open': openSeasons.has(season.number) }"
          viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"
        >
          <polyline points="4,6 8,10 12,6"/>
        </svg>
        <span class="season__title">{{ lang.series.season }} {{ pad(season.number) }}</span>
        <span class="season__meta">
          {{ season.subtitled }} / {{ season.episodes.length }} {{ lang.series.subtitled }}
        </span>
        <button
          class="btn btn--icon"
          :disabled="generatingAll || generatingSeasons.has(season.number) || season.missing === 0"
          :title="generatingSeasons.has(season.number) ? lang.series.queuing : lang.series.generateSeason"
          @click.stop="generateSeason(season.number)"
        >
          <span v-if="generatingSeasons.has(season.number)" class="spinner" />
          <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="6.5" cy="6.5" r="4"/>
            <line x1="9.5" y1="9.5" x2="13.5" y2="13.5"/>
          </svg>
        </button>
        <button
          v-if="season.subtitled > 0"
          class="btn btn--icon btn--icon-danger"
          :disabled="deletingSeasons.has(season.number)"
          :title="lang.series.deleteSeasonSubtitles"
          @click.stop="pendingDelete = { type: 'season', season: season.number }"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="4" y1="4" x2="12" y2="12"/>
            <line x1="12" y1="4" x2="4" y2="12"/>
          </svg>
        </button>
      </div>

      <div v-show="openSeasons.has(season.number)" class="season__body">
        <table class="table">
          <thead>
            <tr>
              <th>{{ lang.series.table.episode }}</th>
              <th>{{ lang.series.table.title }}</th>
              <th>{{ lang.series.table.sourceSrt }}</th>
              <th>{{ settingsStore.targetLangLabel }}</th>
              <th>{{ lang.series.table.actions }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ep in season.episodes" :key="ep.id">
              <td>{{ ep.episode }}</td>
              <td>{{ ep.title }}</td>
              <td>
                <span v-if="ep.source_srt_label" class="badge badge--info">
                  {{ ep.source_srt_label }}
                </span>
                <span v-else class="badge badge--danger">{{ lang.badges.none }}</span>
              </td>
              <td>
                <span :class="ep.has_target_srt ? 'badge badge--success' : 'badge badge--warning'">
                  {{ ep.has_target_srt ? lang.badges.yes : lang.badges.missing }}
                </span>
              </td>
              <td style="display: flex; gap: 6px">
                <button
                  v-if="!ep.has_target_srt"
                  class="btn btn--icon"
                  :disabled="generatingAll || generatingSeasons.has(season.number) || generatingEpisodes.has(ep.id)"
                  :title="lang.actions.generateTitle"
                  @click="generateEpisode(ep.id)"
                >
                  <span v-if="generatingEpisodes.has(ep.id)" class="spinner" />
                  <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="6.5" cy="6.5" r="4"/>
                    <line x1="9.5" y1="9.5" x2="13.5" y2="13.5"/>
                  </svg>
                </button>
                <button
                  v-if="ep.has_target_srt"
                  class="btn btn--icon btn--icon-danger"
                  :title="lang.actions.deleteTitle"
                  @click="pendingDelete = { type: 'episode', id: ep.id, title: ep.title }"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="4" y1="4" x2="12" y2="12"/>
                    <line x1="12" y1="4" x2="4" y2="12"/>
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <ConfirmModal
    v-if="pendingDelete"
    :message="confirmMessage"
    @confirm="confirmDelete"
    @cancel="pendingDelete = null"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { seriesApi } from "@/api";
import type { Episode } from "@/stores/library";
import { lang } from "@/lang";
import { useSettingsStore } from "@/stores/settings";
import { useTasksStore } from "@/stores/tasks";
import ConfirmModal from "@/components/ConfirmModal.vue";

const settingsStore = useSettingsStore();
const tasksStore = useTasksStore();

type PendingDelete =
  | { type: "episode"; id: number; title: string }
  | { type: "season"; season: number }
  | { type: "series" };

interface SeasonGroup {
  number: number;
  episodes: Episode[];
  subtitled: number;
  missing: number;
}

interface SeriesMetadata {
  poster_url: string | null
  overview: string | null
  status: string | null
  last_aired: string | null
  series_path: string | null
}

const props = defineProps<{ name: string }>();
const episodes = ref<Episode[]>([]);
const metadata = ref<SeriesMetadata | null>(null);
const generatingAll = ref(false);
const generatingSeasons = ref(new Set<number>());
const generatingEpisodes = ref(new Set<number>());
const deletingAll = ref(false);
const deletingSeasons = ref(new Set<number>());
const pendingDelete = ref<PendingDelete | null>(null);
const openSeasons = ref(new Set<number>());

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
const missingCount = computed(() => episodes.value.filter(e => !e.has_target_srt).length);

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function statusLabel(status: string): string {
  return (lang.series.status as Record<string, string>)[status] ?? status;
}

const confirmMessage = computed(() => {
  if (!pendingDelete.value) return "";
  if (pendingDelete.value.type === "episode")
    return lang.confirm.deleteSubtitle(pendingDelete.value.title);
  if (pendingDelete.value.type === "season")
    return lang.confirm.deleteSeasonSubtitles(props.name, pendingDelete.value.season);
  return lang.confirm.deleteSeriesSubtitles(props.name);
});

function pad(n: number | null): string {
  return n != null ? String(n).padStart(2, "0") : "??";
}

function toggleSeason(number: number) {
  const next = new Set(openSeasons.value);
  if (next.has(number)) next.delete(number);
  else next.add(number);
  openSeasons.value = next;
}


async function load() {
  const { data } = await seriesApi.detail(props.name);
  episodes.value = data.episodes;
  metadata.value = data.metadata ?? null;
}

async function generateAll() {
  generatingAll.value = true;
  try {
    await seriesApi.generate(props.name);
  } catch {
    generatingAll.value = false;
  }
}

async function generateSeason(seasonNumber: number) {
  generatingSeasons.value = new Set(generatingSeasons.value).add(seasonNumber);
  try {
    await seriesApi.generateSeason(props.name, seasonNumber);
  } catch {
    const next = new Set(generatingSeasons.value);
    next.delete(seasonNumber);
    generatingSeasons.value = next;
  }
}

async function generateEpisode(id: number) {
  generatingEpisodes.value = new Set(generatingEpisodes.value).add(id);
  try {
    await seriesApi.generateEpisode(props.name, id);
  } catch {
    const next = new Set(generatingEpisodes.value);
    next.delete(id);
    generatingEpisodes.value = next;
  }
}

async function confirmDelete() {
  const target = pendingDelete.value;
  pendingDelete.value = null;
  if (!target) return;

  if (target.type === "episode") {
    await seriesApi.deleteEpisodeSubtitle(props.name, target.id);
    await load();
  } else if (target.type === "season") {
    deletingSeasons.value = new Set(deletingSeasons.value).add(target.season);
    try {
      await seriesApi.deleteSeasonSubtitle(props.name, target.season);
      await load();
    } finally {
      const next = new Set(deletingSeasons.value);
      next.delete(target.season);
      deletingSeasons.value = next;
    }
  } else {
    deletingAll.value = true;
    try {
      await seriesApi.deleteSubtitle(props.name);
      await load();
    } finally {
      deletingAll.value = false;
    }
  }
}

watch(() => props.name, () => {
  episodes.value = [];
  openSeasons.value = new Set();
  generatingSeasons.value = new Set();
  generatingEpisodes.value = new Set();
  load();
});

watch(() => tasksStore.scanVersion, load);
watch(() => tasksStore.subtitleVersion, () => {
  generatingAll.value = false;
  generatingSeasons.value = new Set();
  generatingEpisodes.value = new Set();
  load();
});

onMounted(() => {
  load();
  tasksStore.startScanWatcher();
});

onUnmounted(() => tasksStore.stopScanWatcher());
</script>

<style scoped>
.series-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.seasons-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  margin-bottom: 4px;
}


.series-meta {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
  align-items: flex-start;
}

.series-meta__poster {
  width: 120px;
  min-width: 120px;
  border-radius: var(--radius);
  object-fit: cover;
  aspect-ratio: 2/3;
  background: var(--bg-hover);
  display: block;
}

.series-meta__body {
  flex: 1;
  min-width: 0;
}

.series-meta__title {
  margin: 0 0 10px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.series-chips {
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
.chip--muted   { color: var(--text-muted); }

.series-meta__overview {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

.season {
  margin-bottom: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.season__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--bg-card);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;

  &:hover {
    background: var(--bg-hover);
  }
}

.season__chevron {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: var(--text-muted);
  transition: transform 0.2s ease;
}

.season__chevron--open {
  transform: rotate(-90deg);
}

.season__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.season__meta {
  font-size: 13px;
  color: var(--text-muted);
  flex: 1;
}

.season__body {
  border-top: 1px solid var(--border);
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
