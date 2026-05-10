<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore, type TaskStatus } from '@/stores/task'

const router = useRouter()
const taskStore = useTaskStore()

const filter = ref<'all' | 'active' | 'completed' | 'failed'>('all')

const filteredTasks = computed(() => {
  let list = [...taskStore.tasks].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  )
  if (filter.value === 'active') {
    list = list.filter((t) => ['pending', 'running', 'cancelling'].includes(t.status))
  } else if (filter.value === 'completed') {
    list = list.filter((t) => t.status === 'completed')
  } else if (filter.value === 'failed') {
    list = list.filter((t) => t.status === 'failed' || t.status === 'cancelled')
  }
  return list
})

function statusLabel(status: TaskStatus): string {
  const map: Record<string, string> = {
    pending: '待处理',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
    cancelling: '取消中',
  }
  return map[status] || status
}

function statusClass(status: TaskStatus): string {
  const map: Record<string, string> = {
    pending: 'bg-accent/10 text-accent',
    running: 'bg-warning/10 text-warning',
    completed: 'bg-success/10 text-success',
    failed: 'bg-danger/10 text-danger',
    cancelled: 'bg-text-muted/10 text-text-muted',
    cancelling: 'bg-text-muted/10 text-text-muted',
  }
  return map[status] || 'bg-bg-tertiary text-text-muted'
}

function formatTime(iso?: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '-'
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <h1 class="text-2xl font-bold mb-6">任务列表</h1>

    <div class="flex gap-2 mb-6">
      <button
        v-for="f in [
          { key: 'all', label: '全部' },
          { key: 'active', label: '进行中' },
          { key: 'completed', label: '已完成' },
          { key: 'failed', label: '失败' },
        ]"
        :key="f.key"
        class="px-3 py-1.5 text-sm rounded-md border transition-colors"
        :class="
          filter === f.key
            ? 'bg-accent text-white border-accent'
            : 'border-border hover:bg-bg-tertiary'
        "
        @click="filter = f.key as typeof filter"
      >
        {{ f.label }}
      </button>
    </div>

    <div v-if="filteredTasks.length === 0" class="text-center py-16 text-text-muted">
      <p>暂无任务</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="task in filteredTasks"
        :key="task.id"
        class="bg-bg-secondary border border-border rounded-lg p-4 cursor-pointer hover:border-bg-hover transition-colors"
        @click="router.push(`/task/${task.id}`)"
      >
        <div class="flex items-center justify-between mb-2">
          <h3 class="font-semibold">{{ task.title }}</h3>
          <span
            class="text-[11px] font-semibold px-2 py-1 rounded-full uppercase"
            :class="statusClass(task.status)"
          >
            {{ statusLabel(task.status) }}
          </span>
        </div>
        <p class="text-sm text-text-secondary mb-2">服务: {{ task.serviceName }}</p>
        <div class="flex gap-4 text-xs text-text-muted">
          <span>创建: {{ formatTime(task.createdAt) }}</span>
          <span v-if="task.completedAt">完成: {{ formatTime(task.completedAt) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
