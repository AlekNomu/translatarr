<template>
  <header class="app-header">
    <h1 class="app-header__title">{{ pageTitle }}</h1>
    <div class="app-header__actions">
      <button class="btn btn--ghost" @click="scan" :disabled="scanning">
        {{ scanning ? "Scanning..." : "Scan Library" }}
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { useTasksStore } from "@/stores/tasks";

const route = useRoute();
const tasksStore = useTasksStore();
const scanning = ref(false);

const titles: Record<string, string> = {
  "/series": "Series",
  "/movies": "Movies",
  "/history": "History",
  "/settings/general": "Settings",
  "/system/logs": "Logs",
  "/system/status": "Status",
};

const pageTitle = computed(() => {
  for (const [path, title] of Object.entries(titles)) {
    if (route.path.startsWith(path)) return title;
  }
  return "Translatarr";
});

async function scan() {
  scanning.value = true;
  try {
    await tasksStore.triggerScan();
  } finally {
    setTimeout(() => { scanning.value = false; }, 2000);
  }
}
</script>
