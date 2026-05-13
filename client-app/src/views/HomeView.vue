<script setup lang="ts">
import { useServerStore } from '@/stores/server'
import { useUiStore } from '@/stores/ui'
import { computed, onMounted, ref } from 'vue'
import type { ServiceItem } from '@/stores/server'
import { httpFetch } from '@/composables/useHttp'
import { friendlyErrorMessage } from '@/utils/error'
import Skeleton from '@/components/Skeleton.vue'

const serverStore = useServerStore()
const uiStore = useUiStore()

const hasServers = computed(() => serverStore.serverCount > 0)
const cachedServices = computed(() => serverStore.getCachedServices())
const loads = ref<Record<string, {
  capacity?: number
  current_load?: number
  available_slots?: number
  pending_tasks?: number
  running_tasks?: number
} | null>>({})
const fetchError = ref<string | null>(null)
const isRefreshing = ref(false)

async function retryFetch() {
  if (isRefreshing.value) return
  if (!hasServers.value || !serverStore.defaultServer) return
  try {
    isRefreshing.value = true
    uiStore.setLoading(true)
    fetchError.value = null
    await serverStore.fetchServices()
    await fetchLoads()
  } catch (err) {
    fetchError.value = err instanceof Error ? friendlyErrorMessage(err.message) : friendlyErrorMessage(String(err))
  } finally {
    uiStore.setLoading(false)
    isRefreshing.value = false
  }
}

async function fetchLoads() {
  const server = serverStore.defaultServer
  if (!server?.apiKey) return
  const services = cachedServices.value
  if (!services) return
  await Promise.allSettled(services.map(async (svc: ServiceItem) => {
    try {
      const baseUrl = server.serverUrl.replace(/\/$/, '')
      const url = `${baseUrl}/api/v1/client/services/${encodeURIComponent(svc.id)}/load`
      const res = await httpFetch(url, {
        headers: { Authorization: `Bearer ${server.apiKey}` },
      })
      if (res.ok) {
        loads.value[svc.id] = await res.json()
      } else {
        loads.value[svc.id] = null
      }
    } catch (err) {
      loads.value[svc.id] = null
      uiStore.addToast(friendlyErrorMessage(err instanceof Error ? err.message : String(err)), 'error')
    }
  }))
}

onMounted(async () => {
  if (hasServers.value && serverStore.defaultServer) {
    try {
      uiStore.setLoading(true)
      fetchError.value = null
      await serverStore.fetchServices()
      await fetchLoads()
    } catch (err) {
      fetchError.value = err instanceof Error ? friendlyErrorMessage(err.message) : friendlyErrorMessage(String(err))
    } finally {
      uiStore.setLoading(false)
    }
  }
})
</script>

<template>
  <div class="max-w-5xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">服务市场</h1>
      <button
        class="p-1 text-text-secondary hover:text-text-primary transition-colors"
        :class="{ 'animate-spin': isRefreshing }"
        title="刷新"
        aria-label="刷新服务列表"
        @click="retryFetch"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
    </div>

    <!-- Empty state: no servers -->
    <div
      v-if="!hasServers"
      class="flex flex-col items-center justify-center py-24 text-text-muted"
    >
      <div class="text-5xl mb-4">🔌</div>
      <p class="text-lg mb-2">暂无服务器</p>
      <p class="text-sm">请先添加服务器以浏览可用服务</p>
      <router-link
        to="/settings"
        class="mt-4 px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors"
      >
        前往设置添加服务器 →
      </router-link>
    </div>

    <!-- Error state -->
    <div
      v-else-if="fetchError"
      class="flex flex-col items-center justify-center py-24 text-text-muted"
    >
      <div class="text-5xl mb-4">⚠️</div>
      <p class="text-lg mb-2">加载失败</p>
      <p class="text-sm">{{ fetchError }}</p>
      <button
        class="mt-4 px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors"
        @click="retryFetch"
      >
        重试
      </button>
    </div>

    <!-- Skeleton grid: fetching or no cache -->
    <div
      v-else-if="serverStore.isFetching || cachedServices === null"
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
    >
      <div
        v-for="n in 6"
        :key="`sk-${n}`"
        class="bg-bg-secondary border border-border rounded-lg p-4 space-y-3"
      >
        <div class="flex items-start justify-between">
          <Skeleton width="60%" height="18px" />
          <Skeleton width="40px" height="16px" rounded="9999px" />
        </div>
        <Skeleton :rows="2" height="14px" />
        <Skeleton width="40%" height="14px" />
        <Skeleton :rows="2" height="12px" width="70%" />
      </div>
    </div>

    <!-- Empty state: no services available -->
    <div
      v-else-if="cachedServices?.length === 0"
      class="flex flex-col items-center justify-center py-24 text-text-muted"
    >
      <div class="text-5xl mb-4">📭</div>
      <p class="text-lg">当前服务器没有可用服务</p>
    </div>

    <!-- Service grid placeholder -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="service in cachedServices"
        :key="service.id"
        class="bg-bg-secondary border border-border rounded-lg p-4 hover:border-bg-hover transition-colors cursor-pointer"
        @click="$router.push(`/service/${service.id}`)"
      >
        <div class="flex items-start justify-between mb-2">
          <h3 class="font-semibold text-text-primary truncate">{{ service.name }}</h3>
          <span
            class="text-[11px] font-semibold px-1.5 py-0.5 rounded-full uppercase"
            :class="{
              'bg-success/10 text-success': service.agentStatus === 'online',
              'bg-danger/10 text-danger': service.agentStatus === 'offline',
              'bg-warning/10 text-warning': service.agentStatus === 'busy',
            }"
          >
            {{ service.agentStatus }}
          </span>
        </div>
        <p class="text-sm text-text-secondary line-clamp-2 mb-3">
          {{ service.description || '暂无描述' }}
        </p>
        <div class="flex items-center gap-2 text-xs text-text-muted">
          <span
            class="px-1.5 py-0.5 rounded border"
            :class="service.accessType === 'public'
              ? 'border-success/30 text-success'
              : 'border-warning/30 text-warning'"
          >
            {{ service.accessType === 'public' ? '公开' : '受限' }}
          </span>
          <span v-if="!service.hasPermission" class="text-danger">无权限</span>
        </div>
        <div v-if="loads[service.id]" class="mt-2 text-xs text-text-muted flex flex-wrap gap-2">
          <span v-if="loads[service.id]!.capacity != null">容量: {{ loads[service.id]!.capacity }}</span>
          <span v-if="loads[service.id]!.current_load != null">负载: {{ loads[service.id]!.current_load }}</span>
          <span v-if="loads[service.id]!.available_slots != null">可用: {{ loads[service.id]!.available_slots }}</span>
          <span v-if="loads[service.id]!.pending_tasks != null">排队: {{ loads[service.id]!.pending_tasks }}</span>
          <span v-if="loads[service.id]!.running_tasks != null">运行: {{ loads[service.id]!.running_tasks }}</span>
        </div>
        <div v-else-if="loads[service.id] === null" class="mt-2 text-xs text-danger">
          无法获取负载信息
        </div>
        <div v-else-if="service.hasPermission" class="mt-2">
          <Skeleton :rows="2" height="12px" width="80%" />
        </div>
      </div>
    </div>
  </div>
</template>
