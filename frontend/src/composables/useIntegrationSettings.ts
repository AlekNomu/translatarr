import { onMounted, reactive, ref, watch } from "vue";
import { useSettingsStore } from "@/stores/settings";
import { settingsApi } from "@/api";
import { lang } from "@/lang";

export function useIntegrationSettings(
  service: "sonarr" | "radarr" | "jellyfin",
  defaults: Record<string, string>,
  getTestConfig: (form: Record<string, string>) => Record<string, string>,
) {
  const store = useSettingsStore();
  const saving = ref(false);
  const saved = ref(false);
  const testing = ref(false);
  const connectionOk = ref(false);
  const testLabel = ref(lang.settings.testConnection);

  const form = reactive<Record<string, string>>({ ...defaults });

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
    const displayName = service.charAt(0).toUpperCase() + service.slice(1);
    try {
      const { data } = await settingsApi.testConnection(service, getTestConfig(form));
      if (data.ok) {
        connectionOk.value = true;
        testLabel.value = `${displayName} ${data.version}`;
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

  return { form, saving, saved, testing, connectionOk, testLabel, save, testConnection };
}
