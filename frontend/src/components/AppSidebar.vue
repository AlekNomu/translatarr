<template>
  <aside class="sidebar" :class="{ 'sidebar--open': open }">
    <div class="sidebar__logo">
      <img src="/favicon.ico" class="sidebar__logo-icon" alt="" />
      {{ lang.app.name }}
    </div>
    <nav class="sidebar__nav">
      <router-link to="/series" class="nav-item" active-class="active">
        <span class="nav-item__icon">&#x1F4FA;</span> {{ lang.nav.series }}
      </router-link>
      <router-link to="/movies" class="nav-item" active-class="active">
        <span class="nav-item__icon">&#x1F3AC;</span> {{ lang.nav.movies }}
      </router-link>
      <router-link to="/history" class="nav-item" active-class="active">
        <span class="nav-item__icon">&#x1F4DC;</span> {{ lang.nav.history }}
      </router-link>

      <button class="nav-group" :class="{ open: settingsOpen }" @click="settingsOpen = !settingsOpen">
        <span class="nav-item__icon">&#x2699;</span>
        {{ lang.nav.settings }}
        <span class="nav-group__arrow">&#x25BE;</span>
      </button>
      <div class="nav-group__children" :class="{ open: settingsOpen }">
        <router-link to="/settings/general" class="nav-item nav-item--child" active-class="active">
          <span class="nav-item__icon">&#x2699;</span> {{ lang.nav.general }}
        </router-link>
        <router-link to="/settings/sonarr" class="nav-item nav-item--child" active-class="active">
          {{ lang.nav.sonarr }}
        </router-link>
        <router-link to="/settings/radarr" class="nav-item nav-item--child" active-class="active">
          {{ lang.nav.radarr }}
        </router-link>
        <router-link to="/settings/jellyfin" class="nav-item nav-item--child" active-class="active">
          {{ lang.nav.jellyfin }}
        </router-link>
      </div>

      <button class="nav-group" :class="{ open: systemOpen }" @click="systemOpen = !systemOpen">
        <span class="nav-item__icon">&#x1F5A5;</span>
        {{ lang.nav.system }}
        <span class="nav-group__arrow">&#x25BE;</span>
      </button>
      <div class="nav-group__children" :class="{ open: systemOpen }">
        <router-link to="/system/tasks" class="nav-item nav-item--child" active-class="active">
          <span class="nav-item__icon">&#x23F3;</span> {{ lang.nav.tasks }}
        </router-link>
        <router-link to="/system/logs" class="nav-item nav-item--child" active-class="active">
          <span class="nav-item__icon">&#x1F4CB;</span> {{ lang.nav.logs }}
        </router-link>
        <router-link to="/system/status" class="nav-item nav-item--child" active-class="active">
          <span class="nav-item__icon">&#x2139;</span> {{ lang.nav.status }}
        </router-link>
      </div>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { ref, watchEffect } from "vue";
import { useRoute } from "vue-router";
import { lang } from "@/lang";

defineProps<{ open: boolean }>();
defineEmits<{ close: [] }>();

const route = useRoute();
const settingsOpen = ref(false);
const systemOpen = ref(false);

watchEffect(() => {
  settingsOpen.value = route.path.startsWith("/settings");
  systemOpen.value = route.path.startsWith("/system");
});
</script>
