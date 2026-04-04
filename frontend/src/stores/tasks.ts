import { defineStore } from "pinia";
import { ref } from "vue";
import { tasksApi } from "@/api";

export interface Task {
  id: string;
  task_type: string;
  media_id: number | null;
  status: string;
  progress: number;
  detail: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export const useTasksStore = defineStore("tasks", () => {
  const tasks = ref<Task[]>([]);
  const scanVersion = ref(0);
  const subtitleVersion = ref(0);

  let _pollInterval: ReturnType<typeof setInterval> | null = null;
  let _watcherCount = 0;
  let _hadActiveScan = false;
  let _hadActiveSubtitle = false;

  async function fetchTasks() {
    const { data } = await tasksApi.list();
    tasks.value = data;
  }

  async function triggerScan() {
    const { data } = await tasksApi.scan();
    await fetchTasks();
    return data.task_id as string;
  }

  function startScanWatcher() {
    _watcherCount++;
    if (_pollInterval) return;

    // Initialise state on first tick to avoid false positives
    tasksApi.list().then(({ data }) => {
      _hadActiveScan = data.some(
        (t: Task) => t.task_type === "scan" && (t.status === "running" || t.status === "queued"),
      );
      _hadActiveSubtitle = data.some(
        (t: Task) => t.task_type === "generate_subtitle" && (t.status === "running" || t.status === "queued"),
      );
    });

    _pollInterval = setInterval(async () => {
      const { data } = await tasksApi.list();
      const hasActiveScan = data.some(
        (t: Task) => t.task_type === "scan" && (t.status === "running" || t.status === "queued"),
      );
      const hasActiveSubtitle = data.some(
        (t: Task) => t.task_type === "generate_subtitle" && (t.status === "running" || t.status === "queued"),
      );
      if (_hadActiveScan && !hasActiveScan) {
        scanVersion.value++;
      }
      if (_hadActiveSubtitle && !hasActiveSubtitle) {
        subtitleVersion.value++;
      }
      _hadActiveScan = hasActiveScan;
      _hadActiveSubtitle = hasActiveSubtitle;
    }, 3000);
  }

  function stopScanWatcher() {
    _watcherCount = Math.max(0, _watcherCount - 1);
    if (_watcherCount === 0 && _pollInterval) {
      clearInterval(_pollInterval);
      _pollInterval = null;
    }
  }

  return { tasks, scanVersion, subtitleVersion, fetchTasks, triggerScan, startScanWatcher, stopScanWatcher };
});
