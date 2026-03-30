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

  async function fetchTasks() {
    const { data } = await tasksApi.list();
    tasks.value = data;
  }

  async function triggerScan() {
    const { data } = await tasksApi.scan();
    await fetchTasks();
    return data.task_id as string;
  }

  return { tasks, fetchTasks, triggerScan };
});
