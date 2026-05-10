<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()
</script>

<template>
  <div
    class="absolute top-0 left-0 right-0 h-[2px] bg-accent z-50 origin-left transition-transform duration-300"
    :class="{ 'scale-x-100 animate-pulse': uiStore.isLoading, 'scale-x-0': !uiStore.isLoading }"
  />
</template>
