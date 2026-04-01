<template>
  <div>
    <div class="page-actions">
      <button class="btn btn--primary" :disabled="saving || !connectionOk" @click="save">
        {{ saving ? lang.actions.saving : lang.actions.saveSettings }}
      </button>
      <span v-if="saved" style="margin-left: 12px; color: var(--success)">{{ lang.actions.saved }}</span>
      <span v-else-if="!connectionOk" class="save-hint">{{ lang.settings.testRequiredHint }}</span>
    </div>

    <div class="card">
      <form @submit.prevent>
        <div class="form-group">
          <label class="toggle">
            <input
              type="checkbox"
              class="toggle__input"
              v-model="form.sonarr_enabled"
              true-value="1"
              false-value="0"
            />
            <span class="toggle__track"></span>
            <span class="toggle__label">{{ lang.settings.enabled }}</span>
          </label>
        </div>

        <template v-if="form.sonarr_enabled === '1'">
          <div class="form-group">
            <label>{{ lang.settings.host }}</label>
            <input v-model="form.sonarr_host" type="text" class="form-input" placeholder="sonarr" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.port }}</label>
            <input v-model="form.sonarr_port" type="number" class="form-input" style="max-width: 120px" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.httpTimeout }}</label>
            <input v-model="form.sonarr_http_timeout" type="number" class="form-input" style="max-width: 120px" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.apiKey }}</label>
            <input v-model="form.sonarr_api_key" type="text" class="form-input" autocomplete="off" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.seriesPath }}</label>
            <div class="path-input" @click="pickerField = 'series_path'">
              <span class="path-input__icon">&#x1F4C1;</span>
              <span class="path-input__value" :class="{ placeholder: !form.series_path }">
                {{ form.series_path || lang.settings.seriesPathPlaceholder }}
              </span>
            </div>
            <div class="form-help">{{ lang.settings.seriesPathHelp }}</div>
          </div>

          <FolderPicker
            v-if="pickerField"
            :initial-path="form.series_path"
            @select="(p) => { form.series_path = p; pickerField = null; }"
            @cancel="pickerField = null"
          />

          <button type="button" class="btn btn--primary" :disabled="testing" @click="testConnection">
            <span v-if="testing" class="spinner" />
            {{ testLabel }}
          </button>
        </template>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { useSettingsStore } from "@/stores/settings";
import { settingsApi } from "@/api";
import FolderPicker from "@/components/FolderPicker.vue";
import { lang } from "@/lang";

const store = useSettingsStore();
const saving = ref(false);
const saved = ref(false);
const testing = ref(false);
const connectionOk = ref(false);
const testLabel = ref(lang.settings.testConnection);
const pickerField = ref<"series_path" | null>(null);

const form = reactive({
  sonarr_enabled: "0",
  sonarr_host: "",
  sonarr_port: "",
  sonarr_http_timeout: "",
  sonarr_api_key: "",
  series_path: "",
});

watch(form, () => {
  connectionOk.value = false;
  testLabel.value = lang.settings.testConnection;
});

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

async function testConnection() {
  testing.value = true;
  testLabel.value = lang.settings.testConnection;
  try {
    const { data } = await settingsApi.testConnection("sonarr", {
      host: form.sonarr_host,
      port: form.sonarr_port,
      http_timeout: form.sonarr_http_timeout,
      api_key: form.sonarr_api_key,
    });
    if (data.ok) {
      connectionOk.value = true;
      testLabel.value = `Sonarr ${data.version}`;
    } else {
      connectionOk.value = false;
      testLabel.value = lang.settings.testFailed;
      setTimeout(() => { testLabel.value = lang.settings.testConnection; }, 2000);
    }
  } catch {
    connectionOk.value = false;
    testLabel.value = lang.settings.testFailed;
    setTimeout(() => { testLabel.value = lang.settings.testConnection; }, 2000);
  } finally {
    testing.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.save-hint {
  font-size: 0.85rem;
  color: var(--text-muted, #6b7280);
}

/* Toggle slider */
.toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}
.toggle__input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.toggle__track {
  position: relative;
  width: 44px;
  height: 24px;
  background: var(--border, #d1d5db);
  border-radius: 12px;
  transition: background 0.2s;
  flex-shrink: 0;
}
.toggle__track::after {
  content: "";
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
.toggle__input:checked + .toggle__track {
  background: var(--primary, #3b82f6);
}
.toggle__input:checked + .toggle__track::after {
  transform: translateX(20px);
}
.toggle__label {
  font-size: 0.9rem;
}

/* Spinner */
@keyframes spin {
  to { transform: rotate(360deg); }
}
.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}
</style>
