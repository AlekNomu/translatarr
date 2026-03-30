<template>
  <div class="fp-overlay" @click.self="$emit('cancel')">
    <div class="fp">
      <div class="fp__header">
        <span class="fp__title">Select Folder</span>
        <button class="fp__close" @click="$emit('cancel')">&#x2715;</button>
      </div>

      <div class="fp__toolbar">
        <button class="btn btn--ghost" :disabled="parent === null" @click="navigate(parent!)">
          &#x2191; Up
        </button>
        <span class="fp__current">{{ current || "Root" }}</span>
      </div>

      <div class="fp__list">
        <div v-if="loading" class="fp__status">Loading…</div>
        <div v-else-if="dirs.length === 0" class="fp__status">No subdirectories</div>
        <button
          v-for="dir in dirs"
          :key="dir.path"
          class="fp__item"
          @click="navigate(dir.path)"
        >
          <span class="fp__item-icon">&#x1F4C1;</span>
          {{ dir.name }}
        </button>
      </div>

      <div class="fp__footer">
        <span class="fp__selected">{{ current || "/" }}</span>
        <div style="display:flex; gap:8px">
          <button class="btn btn--ghost" @click="$emit('cancel')">Cancel</button>
          <button class="btn btn--primary" :disabled="!current" @click="$emit('select', current)">
            Select
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import axios from "axios";

const props = defineProps<{ initialPath?: string }>();
const emit = defineEmits<{
  (e: "select", path: string): void;
  (e: "cancel"): void;
}>();

const current = ref(props.initialPath ?? "");
const parent = ref<string | null>(null);
const dirs = ref<{ name: string; path: string }[]>([]);
const loading = ref(false);

async function navigate(path: string | null) {
  if (path === null) return;
  loading.value = true;
  try {
    const { data } = await axios.get("/api/settings/browse", { params: { path } });
    current.value = data.current;
    parent.value = data.parent;
    dirs.value = data.dirs;
  } finally {
    loading.value = false;
  }
}

onMounted(() => navigate(current.value));
</script>
