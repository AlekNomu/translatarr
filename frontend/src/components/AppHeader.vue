<template>
  <header class="app-header">
    <div style="display: flex; align-items: center; gap: 12px;">
      <button class="hamburger" @click="emit('toggle-sidebar')" :aria-label="'Menu'">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <line x1="2" y1="4.5" x2="16" y2="4.5"/>
          <line x1="2" y1="9" x2="16" y2="9"/>
          <line x1="2" y1="13.5" x2="16" y2="13.5"/>
        </svg>
      </button>
      <h1 class="app-header__title">{{ pageTitle }}</h1>
    </div>
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

const emit = defineEmits<{ "toggle-sidebar": [] }>();

const route = useRoute();
const tasksStore = useTasksStore();
const scanning = ref(false);

const titles: Record<string, string> = {
  "/series": lang.nav.series,
  "/movies": lang.nav.movies,
  "/history": lang.nav.history,
  "/settings/general":  lang.nav.settings,
  "/settings/sonarr":   lang.nav.sonarr,
  "/settings/radarr":   lang.nav.radarr,
  "/settings/jellyfin": lang.nav.jellyfin,
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
