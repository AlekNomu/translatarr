<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px">
      <div style="display: flex; gap: 8px">
        <button class="btn btn--ghost" @click="clearDisplay">{{ lang.actions.clearDisplay }}</button>
      </div>
      <span class="badge badge--info" v-if="connected">{{ lang.badges.live }}</span>
      <span class="badge badge--danger" v-else>{{ lang.badges.disconnected }}</span>
    </div>

    <div class="log-console" ref="consoleEl">
      <div
        v-for="(entry, i) in entries"
        :key="i"
        :class="['log-entry', `log-entry--${entry.level}`]"
      >{{ formatDate(entry.timestamp) }} [{{ entry.level }}] {{ entry.message }}</div>
      <div v-if="!entries.length" style="color: var(--text-muted)">{{ lang.systemLogs.waitingForOutput }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick } from "vue";
import { systemApi } from "@/api";
import { lang } from "@/lang";

interface LogEntry {
  timestamp: number;
  level: string;
  message: string;
}

const entries = ref<LogEntry[]>([]);
const connected = ref(false);
const consoleEl = ref<HTMLElement | null>(null);
let es: EventSource | null = null;

function formatDate(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString();
}

function clearDisplay() {
  entries.value = [];
}

function scrollToBottom() {
  nextTick(() => {
    if (consoleEl.value) {
      consoleEl.value.scrollTop = consoleEl.value.scrollHeight;
    }
  });
}

let _reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

function connect() {
  es = new EventSource("/api/system/logs");
  es.onopen = () => { connected.value = true; };
  es.onmessage = (event) => {
    const entry: LogEntry = JSON.parse(event.data);
    entries.value.push(entry);
    if (entries.value.length > 1000) entries.value.shift();
    scrollToBottom();
  };
  es.onerror = () => {
    connected.value = false;
    es?.close();
    es = null;
    _reconnectTimeout = setTimeout(connect, 5000);
  };
}

onMounted(async () => {
  const { data } = await systemApi.recentLogs();
  entries.value = data;
  scrollToBottom();
  connect();
});

onUnmounted(() => {
  if (_reconnectTimeout) clearTimeout(_reconnectTimeout);
  es?.close();
});
</script>
