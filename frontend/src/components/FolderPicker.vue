<template>
  <div class="fp-overlay" @click.self="$emit('cancel')">
    <div class="fp">
      <div class="fp__header">
        <span class="fp__title">{{ lang.folderPicker.title }}</span>
        <button class="fp__close" @click="$emit('cancel')">&#x2715;</button>
      </div>

      <div class="fp__toolbar">
        <button class="btn btn--ghost" :disabled="parent === null" @click="navigate(parent!)">
          &#x2191; {{ lang.folderPicker.up }}
        </button>
        <span class="fp__current">{{ current || lang.folderPicker.root }}</span>
      </div>

      <div class="fp__list">
        <div v-if="loading" class="fp__status">{{ lang.folderPicker.loading }}</div>
        <div v-else-if="dirs.length === 0" class="fp__status">{{ lang.folderPicker.noSubdirectories }}</div>
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
          <button class="btn btn--ghost" @click="$emit('cancel')">{{ lang.folderPicker.cancel }}</button>
          <button class="btn btn--primary" :disabled="!current" @click="$emit('select', current)">
            {{ lang.folderPicker.select }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import axios from "axios";
import { lang } from "@/lang";

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
