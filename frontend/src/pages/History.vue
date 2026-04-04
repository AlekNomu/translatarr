<template>
  <div>
    <div style="margin-bottom: 16px; display: flex; gap: 8px">
      <button
        v-for="f in filters"
        :key="f.value"
        :class="['btn', filter === f.value ? 'btn--primary' : 'btn--ghost']"
        @click="setFilter(f.value)"
      >
        {{ f.label }}
      </button>
    </div>

    <table v-if="items.length" class="table">
      <thead>
        <tr>
          <th>{{ lang.history.table.date }}</th>
          <th>{{ lang.history.table.file }}</th>
          <th>{{ lang.history.table.action }}</th>
          <th>{{ lang.history.table.detail }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>{{ formatDate(item.created_at) }}</td>
          <td>{{ item.media_title || basename(item.file_path) }}</td>
          <td>
            <span :class="actionBadge(item.action)">{{ item.action }}</span>
          </td>
          <td class="card__meta">{{ item.detail || lang.systemTasks.noValue }}</td>
        </tr>
      </tbody>
    </table>

    <div v-else class="empty-state">
      <div class="empty-state__title">{{ lang.history.empty }}</div>
    </div>

    <div v-if="total > perPage" class="pagination">
      <button class="btn btn--ghost" :disabled="page <= 1" @click="page--; load()">{{ lang.history.prev }}</button>
      <span class="pagination__info">Page {{ page }} of {{ Math.ceil(total / perPage) }}</span>
      <button class="btn btn--ghost" :disabled="page * perPage >= total" @click="page++; load()">{{ lang.history.next }}</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { historyApi } from "@/api";
import { lang } from "@/lang";

interface HistoryItem {
  id: number;
  media_id: number | null;
  file_path: string;
  action: string;
  target_lang: string;
  detail: string | null;
  created_at: string;
  media_title: string | null;
  series_name: string | null;
}

const items = ref<HistoryItem[]>([]);
const total = ref(0);
const page = ref(1);
const perPage = 50;
const filter = ref("");

const filters = [
  { label: lang.history.filters.all, value: "" },
  { label: lang.history.filters.translated, value: "translated" },
  { label: lang.history.filters.transcribed, value: "transcribed" },
  { label: lang.history.filters.failed, value: "failed" },
];

function setFilter(f: string) {
  filter.value = f;
  page.value = 1;
  load();
}

async function load() {
  const params: Record<string, string | number> = { page: page.value, per_page: perPage };
  if (filter.value) params.action = filter.value;
  const { data } = await historyApi.list(params);
  items.value = data.items;
  total.value = data.total;
}

function formatDate(d: string): string {
  return new Date(d + "Z").toLocaleString();
}

function basename(path: string): string {
  return path.split("/").pop() || path;
}

function actionBadge(action: string): string {
  const map: Record<string, string> = {
    translated: "badge badge--success",
    transcribed: "badge badge--success",
    resynced: "badge badge--info",
    skipped: "badge badge--warning",
    failed: "badge badge--danger",
    deleted: "badge badge--danger",
  };
  return map[action] || "badge";
}

onMounted(load);
</script>
