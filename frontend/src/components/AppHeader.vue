<template>
  <header class="app-header">
    <h1 class="app-header__title">{{ pageTitle }}</h1>
    <div class="app-header__actions">
      <SearchBox />
      <button class="btn btn--ghost" @click="scan" :disabled="scanning">
        {{ scanning ? lang.header.scanning : lang.header.scanLibrary }}
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { useTasksStore } from "@/stores/tasks";
import { lang } from "@/lang";
import SearchBox from "@/components/SearchBox.vue";

const route = useRoute();
const tasksStore = useTasksStore();
const scanning = ref(false);

const titles: Record<string, string> = {
  "/series": lang.nav.series,
  "/movies": lang.nav.movies,
  "/history": lang.nav.history,
  "/settings/general": lang.nav.settings,
  "/system/logs": lang.nav.logs,
  "/system/status": lang.nav.status,
  "/system/tasks": lang.nav.tasks,
};

const pageTitle = computed(() => {
  for (const [path, title] of Object.entries(titles)) {
    if (route.path.startsWith(path)) return title;
  }
  return lang.app.name;
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
