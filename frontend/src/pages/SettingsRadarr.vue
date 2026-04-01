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
              v-model="form.radarr_enabled"
              true-value="1"
              false-value="0"
            />
            <span class="toggle__track"></span>
            <span class="toggle__label">{{ lang.settings.enabled }}</span>
          </label>
        </div>

        <template v-if="form.radarr_enabled === '1'">
          <div class="form-group">
            <label>{{ lang.settings.host }}</label>
            <input v-model="form.radarr_host" type="text" class="form-input" placeholder="radarr" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.port }}</label>
            <input v-model="form.radarr_port" type="number" class="form-input" style="max-width: 120px" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.httpTimeout }}</label>
            <input v-model="form.radarr_http_timeout" type="number" class="form-input" style="max-width: 120px" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.apiKey }}</label>
            <input v-model="form.radarr_api_key" type="text" class="form-input" autocomplete="off" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.moviesPath }}</label>
            <div class="path-input" @click="pickerField = 'movies_path'">
              <span class="path-input__icon">&#x1F4C1;</span>
              <span class="path-input__value" :class="{ placeholder: !form.movies_path }">
                {{ form.movies_path || lang.settings.moviesPathPlaceholder }}
              </span>
            </div>
            <div class="form-help">{{ lang.settings.moviesPathHelp }}</div>
          </div>

          <FolderPicker
            v-if="pickerField"
            :initial-path="form.movies_path"
            @select="(p) => { form.movies_path = p; pickerField = null; }"
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
const pickerField = ref<"movies_path" | null>(null);

const form = reactive({
  radarr_enabled: "0",
  radarr_host: "",
  radarr_port: "",
  radarr_http_timeout: "",
  radarr_api_key: "",
  movies_path: "",
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
    const { data } = await settingsApi.testConnection("radarr", {
      host: form.radarr_host,
      port: form.radarr_port,
      http_timeout: form.radarr_http_timeout,
      api_key: form.radarr_api_key,
    });
    if (data.ok) {
      connectionOk.value = true;
      testLabel.value = `Radarr ${data.version}`;
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
