<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useTaskStore } from '@/stores/task'
import { useUiStore } from '@/stores/ui'
const router = useRouter()
const route = useRoute()
const taskStore = useTaskStore()
const uiStore = useUiStore()

const navItems = [
  { name: 'home', label: '服务市场', icon: '🏠' },
  { name: 'tasks', label: '任务列表', icon: '📋' },
  { name: 'settings', label: '设置', icon: '⚙️' },
]

const activeTab = computed(() => {
  if (route.path === '/') return 'home'
  if (route.path.startsWith('/task')) return 'tasks'
  if (route.path.startsWith('/settings')) return 'settings'
  return ''
})

const activeTaskCount = computed(() => taskStore.activeTaskCount)

function navigateTo(name: string) {
  uiStore.setCurrentTab(name)
  if (name === 'home') router.push('/')
  else if (name === 'tasks') router.push('/tasks')
  else if (name === 'settings') router.push('/settings')
}

function isActive(name: string): boolean {
  return activeTab.value === name
}
</script>

<template>
  <nav class="w-16 flex-shrink-0 bg-bg-secondary border-r border-border flex flex-col items-center py-4 z-20">
    <!-- Logo -->
    <div class="mb-6 text-xl font-bold select-none cursor-pointer" @click="navigateTo('home')">
      OA
    </div>

    <!-- Nav Items -->
    <div class="flex flex-col gap-2 flex-1 w-full px-2">
      <button
        v-for="item in navItems"
        :key="item.name"
        class="relative flex flex-col items-center justify-center gap-1 py-2 rounded-md transition-colors text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
        :class="{ 'bg-bg-tertiary text-text-primary': isActive(item.name) }"
        @click="navigateTo(item.name)"
      >
        <span class="text-xl">{{ item.icon }}</span>
        <span class="text-[10px] font-medium">{{ item.label }}</span>
        <!-- Red badge for active tasks on task list icon -->
        <span
          v-if="item.name === 'tasks' && activeTaskCount > 0"
          class="absolute top-1 right-1 min-w-[16px] h-4 px-1 bg-danger text-white text-[10px] font-bold rounded-full flex items-center justify-center"
        >
          {{ activeTaskCount }}
        </span>
      </button>
    </div>


  </nav>
</template>
