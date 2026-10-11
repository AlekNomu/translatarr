import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { settingsApi } from "@/api";
import { LANGUAGE_NAMES } from "@/lang";

export interface ProviderField {
  key: string;
  label: string;
  kind: "text" | "secret" | "toggle";
  required: boolean;
  help: string;
  placeholder: string;
}

export interface TranslationProvider {
  label: string;
  description: string;
  supports_auto: boolean;
  order: number;
  fields: ProviderField[];
}

export const useSettingsStore = defineStore("settings", () => {
  const settings = ref<Record<string, string>>({});
  const whisperModels = ref<Record<string, { label: string; description: string }>>({});
  const translationProviders = ref<Record<string, TranslationProvider>>({});

  const targetLangLabel = computed(() => {
    const code = settings.value.target_lang ?? "fr";
    const name = LANGUAGE_NAMES[code] ?? code.toUpperCase();
    return `${name} Subtitle`;
  });

  async function fetch() {
    const { data } = await settingsApi.get();
    settings.value = data.settings;
    whisperModels.value = data.whisper_models;
    translationProviders.value = data.translation_providers ?? {};
  }

  async function save(updates: Record<string, string>) {
    await settingsApi.update(updates);
    Object.assign(settings.value, updates);
  }

  return {
    settings,
    whisperModels,
    translationProviders,
    targetLangLabel,
    fetch,
    save,
  };
});
