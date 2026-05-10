<script setup lang="ts">
interface Props {
  rows?: number
  width?: string
  height?: string
  circle?: boolean
  rounded?: string
}
withDefaults(defineProps<Props>(), {
  rows: 1,
  width: '100%',
  height: '16px',
  circle: false,
  rounded: '4px',
})
</script>

<template>
  <div class="space-y-2">
    <div
      v-for="i in rows"
      :key="i"
      class="animate-pulse bg-bg-tertiary"
      :style="{
        width: circle ? height : width,
        height: height,
        borderRadius: circle ? '50%' : rounded,
      }"
    />
  </div>
</template>
