import { defineStore } from "pinia";
import { ref } from "vue";
import { settingsApi } from "@/api";

export const useSettingsStore = defineStore("settings", () => {
  const settings = ref<Record<string, string>>({});
  const whisperModels = ref<Record<string, { label: string; description: string }>>({});

  async function fetch() {
    const { data } = await settingsApi.get();
    settings.value = data.settings;
    whisperModels.value = data.whisper_models;
  }

  async function save(updates: Record<string, string>) {
    await settingsApi.update(updates);
    Object.assign(settings.value, updates);
  }

  return { settings, whisperModels, fetch, save };
});
