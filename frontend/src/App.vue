<template>
  <div class="app-layout">
    <AppSidebar :open="sidebarOpen" @close="sidebarOpen = false" />
    <div
      v-if="sidebarOpen"
      class="sidebar-overlay"
      @click="sidebarOpen = false"
    />
    <div class="app-main">
      <AppHeader @toggle-sidebar="sidebarOpen = !sidebarOpen" />
      <div class="app-content">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { useRoute } from "vue-router";
import AppSidebar from "./components/AppSidebar.vue";
import AppHeader from "./components/AppHeader.vue";
import { useSettingsStore } from "@/stores/settings";

const settingsStore = useSettingsStore();
const route = useRoute();
const sidebarOpen = ref(false);

// Close sidebar on navigation
watch(() => route.path, () => { sidebarOpen.value = false; });

settingsStore.fetch();
</script>
