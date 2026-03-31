<template>
  <div>
    <div class="card" v-if="status">
      <table class="table">
        <tbody>
          <tr>
            <td><strong>{{ lang.systemStatus.version }}</strong></td>
            <td>{{ status.version }}</td>
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

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

onMounted(async () => {
  const { data } = await systemApi.status();
  status.value = data;
});
</script>
