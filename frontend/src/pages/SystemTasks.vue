<template>
  <div>
    <div class="tasks-header">
      <span class="tasks-count">
        {{ tasksStore.tasks.length }} {{ tasksStore.tasks.length === 1 ? lang.systemTasks.task : lang.systemTasks.tasks }}
      </span>
      <button class="btn btn--primary" @click="load">{{ lang.actions.refresh }}</button>
    </div>

    <div v-if="tasksStore.tasks.length === 0" class="empty-state">
      <div class="empty-state__title">{{ lang.systemTasks.noTasks.title }}</div>
      <div class="empty-state__text">{{ lang.systemTasks.noTasks.text }}</div>
    </div>

    <table v-else class="table">
      <thead>
        <tr>
          <th>{{ lang.systemTasks.table.type }}</th>
          <th>{{ lang.systemTasks.table.status }}</th>
          <th>{{ lang.systemTasks.table.progress }}</th>
          <th>{{ lang.systemTasks.table.detail }}</th>
          <th>{{ lang.systemTasks.table.created }}</th>
          <th>{{ lang.systemTasks.table.actions }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in tasksStore.tasks" :key="t.id">
          <td>{{ t.task_type === "generate_subtitle" ? lang.systemTasks.types.subtitle : lang.systemTasks.types.scan }}</td>
          <td>
            <span :class="statusBadge(t.status)">{{ t.status }}</span>
          </td>
          <td>
            <div v-if="t.status === 'running'" class="progress-bar">
              <div class="progress-bar__fill" :style="{ width: t.progress + '%' }" />
            </div>
            <span v-else-if="t.status === 'completed'">{{ lang.systemTasks.completedProgress }}</span>
            <span v-else>{{ lang.systemTasks.noValue }}</span>
          </td>
          <td class="cell--detail">{{ t.detail ?? lang.systemTasks.noValue }}</td>
          <td>{{ formatDate(t.created_at) }}</td>
          <td>
            <button
              v-if="t.status === 'queued'"
              class="btn btn--danger"
              @click="cancel(t.id)"
            >
              {{ lang.actions.cancel }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import { tasksApi } from "@/api";
import { useTasksStore } from "@/stores/tasks";
import { lang } from "@/lang";

const tasksStore = useTasksStore();
let pollInterval: ReturnType<typeof setInterval> | null = null;

async function load() {
  await tasksStore.fetchTasks();
}

async function cancel(id: string) {
  await tasksApi.cancel(id);
  await tasksStore.fetchTasks();
}

function statusBadge(status: string): string {
  const map: Record<string, string> = {
    queued: "badge badge--warning",
    running: "badge badge--info",
    completed: "badge badge--success",
    failed: "badge badge--danger",
    cancelled: "badge",
  };
  return map[status] ?? "badge";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

onMounted(() => {
  load();
  pollInterval = setInterval(() => {
    if (tasksStore.tasks.some(t => t.status === "queued" || t.status === "running")) {
      load();
    }
  }, 3000);
});

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval);
});
</script>

<style scoped>
.tasks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.tasks-count {
  font-size: 13px;
  color: var(--text-muted);
}

.progress-bar {
  width: 80px;
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar__fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.3s;
}

.cell--detail {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
