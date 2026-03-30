<template>
  <div>
    <div class="card">
      <form @submit.prevent="save">
        <div class="form-group">
          <label>Target Language</label>
          <select v-model="form.target_lang" class="form-select">
            <option value="fr">French (fr)</option>
            <option value="es">Spanish (es)</option>
            <option value="de">German (de)</option>
            <option value="it">Italian (it)</option>
            <option value="pt">Portuguese (pt)</option>
          </select>
        </div>

        <div class="form-group">
          <label>Whisper Model</label>
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
          <label>Concurrent Workers</label>
          <input
            v-model="form.workers"
            type="number"
            min="1"
            max="6"
            class="form-input"
            style="max-width: 120px"
          />
          <div class="form-help">Requires a restart to take effect.</div>
        </div>

        <div class="form-group">
          <label>Series Path</label>
          <div class="path-input" @click="openPicker('series_path')">
            <span class="path-input__icon">&#x1F4C1;</span>
            <span class="path-input__value" :class="{ placeholder: !form.series_path }">
              {{ form.series_path || "/tv" }}
            </span>
          </div>
          <div class="form-help">Directory containing your TV series (Sonarr-style structure)</div>
        </div>

        <div class="form-group">
          <label>Movies Path</label>
          <div class="path-input" @click="openPicker('movies_path')">
            <span class="path-input__icon">&#x1F4C1;</span>
            <span class="path-input__value" :class="{ placeholder: !form.movies_path }">
              {{ form.movies_path || "/movies" }}
            </span>
          </div>
          <div class="form-help">Directory containing your movies (Radarr-style structure)</div>
        </div>

        <div class="form-group">
          <label>Scan Interval (minutes)</label>
          <input
            v-model="form.scan_interval_minutes"
            type="number"
            min="0"
            class="form-input"
            style="max-width: 120px"
          />
          <div class="form-help">Set to 0 to disable automatic scanning</div>
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="form.generate_after_scan"
              true-value="1"
              false-value="0"
            />
            Generate subtitles after scan
          </label>
          <div class="form-help">Queue subtitle generation for all media without subtitles at the end of every scan. Disabled by default.</div>
        </div>

        <FolderPicker
          v-if="pickerField"
          :initial-path="form[pickerField]"
          @select="onPickerSelect"
          @cancel="pickerField = null"
        />

        <button type="submit" class="btn btn--primary" :disabled="saving">
          {{ saving ? "Saving..." : "Save Settings" }}
        </button>
        <span v-if="saved" style="margin-left: 12px; color: var(--success)">Saved!</span>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useSettingsStore } from "@/stores/settings";
import FolderPicker from "@/components/FolderPicker.vue";

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
