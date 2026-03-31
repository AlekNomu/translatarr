<template>
  <div>
    <div class="card">
      <form @submit.prevent="save">
        <div class="form-group">
          <label>{{ lang.settings.targetLanguage }}</label>
          <select v-model="form.target_lang" class="form-select">
            <option value="fr">{{ lang.settings.languages.fr }}</option>
            <option value="es">{{ lang.settings.languages.es }}</option>
            <option value="de">{{ lang.settings.languages.de }}</option>
            <option value="it">{{ lang.settings.languages.it }}</option>
            <option value="pt">{{ lang.settings.languages.pt }}</option>
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
          <label>{{ lang.settings.seriesPath }}</label>
          <div class="path-input" @click="openPicker('series_path')">
            <span class="path-input__icon">&#x1F4C1;</span>
            <span class="path-input__value" :class="{ placeholder: !form.series_path }">
              {{ form.series_path || lang.settings.seriesPathPlaceholder }}
            </span>
          </div>
          <div class="form-help">{{ lang.settings.seriesPathHelp }}</div>
        </div>

        <div class="form-group">
          <label>{{ lang.settings.moviesPath }}</label>
          <div class="path-input" @click="openPicker('movies_path')">
            <span class="path-input__icon">&#x1F4C1;</span>
            <span class="path-input__value" :class="{ placeholder: !form.movies_path }">
              {{ form.movies_path || lang.settings.moviesPathPlaceholder }}
            </span>
          </div>
          <div class="form-help">{{ lang.settings.moviesPathHelp }}</div>
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

        <div class="form-group">
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="form.generate_after_scan"
              true-value="1"
              false-value="0"
            />
            {{ lang.settings.generateAfterScan }}
          </label>
          <div class="form-help">{{ lang.settings.generateAfterScanHelp }}</div>
        </div>

        <FolderPicker
          v-if="pickerField"
          :initial-path="form[pickerField]"
          @select="onPickerSelect"
          @cancel="pickerField = null"
        />

        <button type="submit" class="btn btn--primary" :disabled="saving">
          {{ saving ? lang.actions.saving : lang.actions.saveSettings }}
        </button>
        <span v-if="saved" style="margin-left: 12px; color: var(--success)">{{ lang.actions.saved }}</span>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useSettingsStore } from "@/stores/settings";
import FolderPicker from "@/components/FolderPicker.vue";
import { lang } from "@/lang";

const store = useSettingsStore();
const saving = ref(false);
const saved = ref(false);
const pickerField = ref<"series_path" | "movies_path" | null>(null);

function openPicker(field: "series_path" | "movies_path") {
  pickerField.value = field;
}

function onPickerSelect(path: string) {
  if (pickerField.value) form[pickerField.value] = path;
  pickerField.value = null;
}

const form = reactive({
  target_lang: "",
  whisper_model: "",
  workers: "",
  series_path: "",
  movies_path: "",
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
  await store.fetch();
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
