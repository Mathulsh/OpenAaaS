<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()

const typeClasses: Record<string, string> = {
  success: 'border-success/30',
  error: 'border-danger/30',
  info: 'border-accent/30',
}

const typeIcons: Record<string, string> = {
  success: '✓',
  error: '✕',
  info: 'ℹ',
}
</script>

<template>
  <div class="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
    <transition-group name="toast">
      <div
        v-for="toast in uiStore.toastQueue"
        :key="toast.id"
        class="pointer-events-auto bg-bg-secondary border rounded-md px-4 py-3 min-w-[240px] max-w-[360px] shadow-md flex items-start gap-2.5"
        :class="typeClasses[toast.type] || typeClasses.info"
      >
        <span class="text-base flex-shrink-0 mt-0.5">{{ typeIcons[toast.type] || typeIcons.info }}</span>
        <div class="flex-1 text-sm leading-relaxed">{{ toast.message }}</div>
        <button
          class="text-text-muted hover:text-text-primary text-base leading-none flex-shrink-0"
          @click="uiStore.removeToast(toast.id)"
        >
          &times;
        </button>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  transform: translateX(120%);
  opacity: 0;
}
.toast-leave-to {
  transform: translateX(120%);
  opacity: 0;
}
</style>
