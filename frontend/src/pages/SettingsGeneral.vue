<template>
  <div>
    <div class="page-actions">
      <button class="btn btn--primary" :disabled="saving" @click="save">
        {{ saving ? lang.actions.saving : lang.actions.saveSettings }}
      </button>
      <span v-if="saved" style="color: var(--success)">{{ lang.actions.saved }}</span>
    </div>

    <div class="card">
      <div class="form-group">
        <label class="toggle">
          <input
            type="checkbox"
            class="toggle__input"
            v-model="form.generate_after_scan"
            true-value="1"
            false-value="0"
          />
          <span class="toggle__track"></span>
          <span class="toggle__label">{{ lang.settings.generateAutomatically }}</span>
        </label>
        <div class="form-help">{{ lang.settings.generateAfterScanHelp }}</div>
      </div>

      <div class="form-group">
        <label>{{ lang.settings.targetLanguage }}</label>
        <select v-model="form.target_lang" class="form-select">
          <option v-for="(name, code) in LANGUAGE_NAMES" :key="code" :value="code">
            {{ name }} ({{ code }})
          </option>
        </select>
      </div>

      <div class="form-group">
        <label>{{ lang.settings.whisperModel }}</label>
        <select v-model="form.whisper_model" class="form-select">
          <option
            v-for="{ key, info } in sortedWhisperModels"
            :key="key"
            :value="key"
          >
            {{ info.label }}
          </option>
        </select>
        <div class="form-help" v-if="currentModelInfo">
          {{ currentModelInfo.description }}
        </div>
      </div>

      <div class="form-group">
        <label>{{ lang.settings.concurrentWorkers }}</label>
        <input
          v-model="form.workers"
          type="number"
          min="1"
          max="6"
          class="form-input"
          style="max-width: 120px"
        />
        <div class="form-help">{{ lang.settings.workersHelp }}</div>
      </div>

      <div class="form-group">
        <label>{{ lang.settings.scanInterval }}</label>
        <input
          v-model="form.scan_interval_minutes"
          type="number"
          min="0"
          class="form-input"
          style="max-width: 120px"
        />
        <div class="form-help">{{ lang.settings.scanIntervalHelp }}</div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useSettingsStore } from "@/stores/settings";
import { lang, LANGUAGE_NAMES } from "@/lang";

const store = useSettingsStore();
const saving = ref(false);
const saved = ref(false);

const form = reactive({
  target_lang: "",
  whisper_model: "",
  workers: "",
  scan_interval_minutes: "",
  generate_after_scan: "0",
});

const MODEL_ORDER = ["tiny", "base", "small", "medium", "large"];

const sortedWhisperModels = computed(() =>
  MODEL_ORDER
    .filter(k => k in store.whisperModels)
    .map(k => ({ key: k, info: store.whisperModels[k] }))
);

const currentModelInfo = computed(() =>
  store.whisperModels[form.whisper_model] || null
);

async function load() {
  if (!Object.keys(store.settings).length) await store.fetch();
  Object.assign(form, store.settings);
}

async function save() {
  saving.value = true;
  saved.value = false;
  try {
    await store.save({ ...form });
    saved.value = true;
    setTimeout(() => { saved.value = false; }, 3000);
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>
