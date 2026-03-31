<template>
  <Teleport to="body">
    <div class="confirm-overlay" @click.self="$emit('cancel')">
      <div class="confirm">
        <div class="confirm__body">{{ message }}</div>
        <div class="confirm__actions">
          <button class="btn btn--ghost" @click="$emit('cancel')">
            {{ lang.actions.cancel }}
          </button>
          <button class="btn btn--danger" @click="$emit('confirm')">
            {{ lang.actions.delete }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { lang } from "@/lang";

defineProps<{ message: string }>();
defineEmits<{ confirm: []; cancel: [] }>();
</script>
