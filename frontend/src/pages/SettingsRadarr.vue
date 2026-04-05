<template>
  <div>
    <div class="page-actions">
      <button class="btn btn--primary" :disabled="saving || !connectionOk" @click="save">
        {{ saving ? lang.actions.saving : lang.actions.saveSettings }}
      </button>
      <span v-if="saved" style="color: var(--success)">{{ lang.actions.saved }}</span>
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
import { ref } from "vue";
import { useIntegrationSettings } from "@/composables/useIntegrationSettings";
import FolderPicker from "@/components/FolderPicker.vue";
import { lang } from "@/lang";

const pickerField = ref<"movies_path" | null>(null);

const { form, saving, saved, testing, connectionOk, testLabel, save, testConnection } =
  useIntegrationSettings(
    "radarr",
    { radarr_enabled: "0", radarr_host: "", radarr_port: "", radarr_http_timeout: "", radarr_api_key: "", movies_path: "" },
    (f) => ({ host: f.radarr_host, port: f.radarr_port, http_timeout: f.radarr_http_timeout, api_key: f.radarr_api_key }),
  );
</script>

<style scoped>
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
