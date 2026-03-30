<template>
  <div v-if="activeTasks.length" class="task-progress">
    <span class="badge badge--info">
      {{ activeTasks.length }} task{{ activeTasks.length > 1 ? "s" : "" }} running
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useTasksStore } from "@/stores/tasks";

const store = useTasksStore();

const activeTasks = computed(() =>
  store.tasks.filter((t) => t.status === "running" || t.status === "queued")
);

onMounted(() => store.fetchTasks());
</script>
