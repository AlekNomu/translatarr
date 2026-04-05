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
              v-model="form.jellyfin_enabled"
              true-value="1"
              false-value="0"
            />
            <span class="toggle__track"></span>
            <span class="toggle__label">{{ lang.settings.enabled }}</span>
          </label>
        </div>

        <template v-if="form.jellyfin_enabled === '1'">
          <div class="form-group">
            <label>{{ lang.settings.host }}</label>
            <input v-model="form.jellyfin_host" type="text" class="form-input" placeholder="jellyfin" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.port }}</label>
            <input v-model="form.jellyfin_port" type="number" class="form-input" style="max-width: 120px" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.httpTimeout }}</label>
            <input v-model="form.jellyfin_http_timeout" type="number" class="form-input" style="max-width: 120px" />
          </div>

          <div class="form-group">
            <label>{{ lang.settings.apiKey }}</label>
            <input v-model="form.jellyfin_api_key" type="text" class="form-input" autocomplete="off" />
          </div>

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
import { useIntegrationSettings } from "@/composables/useIntegrationSettings";
import { lang } from "@/lang";

const { form, saving, saved, testing, connectionOk, testLabel, save, testConnection } =
  useIntegrationSettings(
    "jellyfin",
    { jellyfin_enabled: "0", jellyfin_host: "", jellyfin_port: "", jellyfin_http_timeout: "", jellyfin_api_key: "" },
    (f) => ({ host: f.jellyfin_host, port: f.jellyfin_port, http_timeout: f.jellyfin_http_timeout, api_key: f.jellyfin_api_key }),
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
