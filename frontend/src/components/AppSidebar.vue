<template>
  <aside class="sidebar">
    <div class="sidebar__logo">
      Translatarr
    </div>
    <nav class="sidebar__nav">
      <router-link to="/series" class="nav-item" active-class="active">
        <span class="nav-item__icon">&#x1F4FA;</span> Series
      </router-link>
      <router-link to="/movies" class="nav-item" active-class="active">
        <span class="nav-item__icon">&#x1F3AC;</span> Movies
      </router-link>
      <router-link to="/history" class="nav-item" active-class="active">
        <span class="nav-item__icon">&#x1F4DC;</span> History
      </router-link>

      <button class="nav-group" :class="{ open: settingsOpen }" @click="settingsOpen = !settingsOpen">
        <span class="nav-item__icon">&#x2699;</span>
        Settings
        <span class="nav-group__arrow">&#x25BE;</span>
      </button>
      <div class="nav-group__children" :class="{ open: settingsOpen }">
        <router-link to="/settings/general" class="nav-item nav-item--child" active-class="active">
          <span class="nav-item__icon">&#x2699;</span> General
        </router-link>
      </div>

      <button class="nav-group" :class="{ open: systemOpen }" @click="systemOpen = !systemOpen">
        <span class="nav-item__icon">&#x1F5A5;</span>
        System
        <span class="nav-group__arrow">&#x25BE;</span>
      </button>
      <div class="nav-group__children" :class="{ open: systemOpen }">
        <router-link to="/system/tasks" class="nav-item nav-item--child" active-class="active">
          <span class="nav-item__icon">&#x23F3;</span> Tasks
        </router-link>
        <router-link to="/system/logs" class="nav-item nav-item--child" active-class="active">
          <span class="nav-item__icon">&#x1F4CB;</span> Logs
        </router-link>
        <router-link to="/system/status" class="nav-item nav-item--child" active-class="active">
          <span class="nav-item__icon">&#x2139;</span> Status
        </router-link>
      </div>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { ref, watchEffect } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const settingsOpen = ref(false);
const systemOpen = ref(false);

watchEffect(() => {
  if (route.path.startsWith("/settings")) settingsOpen.value = true;
  if (route.path.startsWith("/system")) systemOpen.value = true;
});
</script>
