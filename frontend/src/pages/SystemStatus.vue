<template>
  <div>
    <div class="card" v-if="status">
      <table class="table">
        <tbody>
          <tr>
            <td><strong>Version</strong></td>
            <td>{{ status.version }}</td>
          </tr>
          <tr>
            <td><strong>Python</strong></td>
            <td>{{ status.python_version }}</td>
          </tr>
          <tr>
            <td><strong>Uptime</strong></td>
            <td>{{ formatUptime(status.uptime_seconds) }}</td>
          </tr>
          <tr>
            <td><strong>ffmpeg</strong></td>
            <td>
              <span :class="status.ffmpeg_available ? 'badge badge--success' : 'badge badge--danger'">
                {{ status.ffmpeg_available ? "Available" : "Not found" }}
              </span>
            </td>
          </tr>
          <tr>
            <td><strong>Whisper</strong></td>
            <td>
              <span :class="status.whisper_available ? 'badge badge--success' : 'badge badge--danger'">
                {{ status.whisper_available ? "Installed" : "Not installed" }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state">
      <div class="empty-state__title">Loading status…</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { systemApi } from "@/api";

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
