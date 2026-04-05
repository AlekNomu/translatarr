<template>
  <div>
    <div class="card" v-if="status">
      <table class="table">
        <tbody>
          <tr>
            <td><strong>{{ lang.systemStatus.version }}</strong></td>
            <td>
              {{ status.version }}
              <span v-if="updateAvailable" class="badge badge--warning update-badge">
                ⚠ {{ lang.systemStatus.updateAvailable(latestVersion!) }}
              </span>
            </td>
          </tr>
          <tr>
            <td><strong>{{ lang.systemStatus.python }}</strong></td>
            <td>{{ status.python_version }}</td>
          </tr>
          <tr>
            <td><strong>{{ lang.systemStatus.uptime }}</strong></td>
            <td>{{ formatUptime(status.uptime_seconds) }}</td>
          </tr>
          <tr>
            <td><strong>{{ lang.systemStatus.ffmpeg }}</strong></td>
            <td>
              <span :class="status.ffmpeg_available ? 'badge badge--success' : 'badge badge--danger'">
                {{ status.ffmpeg_available ? lang.badges.available : lang.badges.notFound }}
              </span>
            </td>
          </tr>
          <tr>
            <td><strong>{{ lang.systemStatus.whisper }}</strong></td>
            <td>
              <span :class="status.whisper_available ? 'badge badge--success' : 'badge badge--danger'">
                {{ status.whisper_available ? lang.badges.installed : lang.badges.notInstalled }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state">
      <div class="empty-state__title">{{ lang.systemStatus.loading }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { systemApi } from "@/api";
import { lang } from "@/lang";

interface Status {
  version: string;
  python_version: string;
  uptime_seconds: number;
  ffmpeg_available: boolean;
  whisper_available: boolean;
}

const status = ref<Status | null>(null);
const latestVersion = ref<string | null>(null);
const updateAvailable = ref(false);

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function isNewerVersion(remote: string, local: string): boolean {
  const parse = (v: string) => v.split(".").map(Number);
  const [rMaj, rMin, rPat] = parse(remote);
  const [lMaj, lMin, lPat] = parse(local);
  if (rMaj !== lMaj) return rMaj > lMaj;
  if (rMin !== lMin) return rMin > lMin;
  return rPat > lPat;
}

onMounted(async () => {
  const { data } = await systemApi.status();
  status.value = data;

  try {
    const res = await fetch("https://api.github.com/repos/aleknomu/translatarr/releases/latest");
    if (res.ok) {
      const json = await res.json();
      const tag = (json.tag_name as string).replace(/^v/, "");
      if (isNewerVersion(tag, data.version)) {
        latestVersion.value = tag;
        updateAvailable.value = true;
      }
    }
  } catch {
    // silently ignore if GitHub is unreachable
  }
});
</script>

<style scoped>
.update-badge {
  margin-left: 8px;
}
</style>
