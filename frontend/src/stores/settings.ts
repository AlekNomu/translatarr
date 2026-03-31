import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { settingsApi } from "@/api";
import { LANGUAGE_NAMES } from "@/lang";

export const useSettingsStore = defineStore("settings", () => {
  const settings = ref<Record<string, string>>({});
  const whisperModels = ref<Record<string, { label: string; description: string }>>({});

  const targetLangLabel = computed(() => {
    const code = settings.value.target_lang ?? "fr";
    const name = LANGUAGE_NAMES[code] ?? code.toUpperCase();
    return `${name} Subtitle`;
  });

  async function fetch() {
    const { data } = await settingsApi.get();
    settings.value = data.settings;
    whisperModels.value = data.whisper_models;
  }

  async function save(updates: Record<string, string>) {
    await settingsApi.update(updates);
    Object.assign(settings.value, updates);
  }

  return { settings, whisperModels, targetLangLabel, fetch, save };
});
