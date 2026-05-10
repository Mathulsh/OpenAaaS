<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useServerStore } from '@/stores/server'
import { useTaskStore } from '@/stores/task'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const router = useRouter()
const serverStore = useServerStore()
const taskStore = useTaskStore()
const uiStore = useUiStore()

const serviceId = computed(() => String(route.params.serviceId))
const service = computed(() => {
  for (const cache of Object.values(serverStore.services)) {
    const found = cache.items.find((s) => s.id === serviceId.value)
    if (found) return found
  }
  return undefined
})

const title = ref('')
const taskPrompt = ref('')
const outputPrompt = ref('')
const files = ref<FileList | null>(null)
const step = ref(1)
const dragOver = ref(false)
const isLoadingService = ref(false)
const serviceLoadError = ref<string | null>(null)

function handleDrop(event: DragEvent) {
  dragOver.value = false
  if (event.dataTransfer?.files) {
    files.value = event.dataTransfer.files
  }
}

async function submit() {
  if (!service.value) {
    uiStore.addToast('服务信息不存在', 'error')
    return
  }
  if (!serverStore.defaultServer) {
    uiStore.addToast('未设置默认服务器', 'error')
    return
  }
  try {
    uiStore.setLoading(true)
    const taskId = await taskStore.submitTask({
      serverAlias: serverStore.defaultServer.alias,
      serviceId: serviceId.value,
      serviceName: service.value.name,
      title: title.value || '未命名任务',
      taskPrompt: taskPrompt.value,
      outputPrompt: outputPrompt.value,
      files: files.value ? Array.from(files.value) : undefined,
    })
    uiStore.addToast('任务提交成功', 'success')
    router.push(`/task/${taskId}`)
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    uiStore.addToast(msg, 'error')
  } finally {
    uiStore.setLoading(false)
  }
}

function nextStep() {
  if (step.value === 1) {
    if (!taskPrompt.value.trim()) {
      uiStore.addToast('任务描述不能为空', 'error')
      return
    }
    if (!outputPrompt.value.trim()) {
      uiStore.addToast('输出要求不能为空', 'error')
      return
    }
  }
  if (step.value < 2) step.value++
}

function prevStep() {
  if (step.value > 1) step.value--
}

onMounted(async () => {
  if (!service.value) {
    isLoadingService.value = true
    serviceLoadError.value = null
    try {
      await serverStore.fetchServices()
      if (!service.value) {
        serviceLoadError.value = '未找到该服务，可能已被删除或您没有访问权限'
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      serviceLoadError.value = msg
    } finally {
      isLoadingService.value = false
    }
  }
})
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div class="mb-6">
      <router-link
        :to="`/service/${serviceId}`"
        class="text-sm text-text-secondary hover:text-text-primary mb-2 inline-block"
      >
        ← 返回服务详情
      </router-link>
      <h1 class="text-2xl font-bold mt-2">提交任务</h1>
    </div>

    <!-- Step indicator -->
    <div class="flex items-center gap-2 mb-6">
      <div
        v-for="i in 2"
        :key="i"
        class="h-1.5 flex-1 rounded-full transition-colors"
        :class="i <= step ? 'bg-accent' : 'bg-bg-tertiary'"
      />
    </div>

    <div class="bg-bg-secondary border border-border rounded-lg p-6">
      <!-- Loading state -->
      <div v-if="isLoadingService" class="py-8 text-center text-text-secondary text-sm">
        加载服务信息中...
      </div>
      <div v-else-if="serviceLoadError" class="py-8 text-center text-danger text-sm">
        {{ serviceLoadError }}
      </div>

      <!-- Step 1: Fill Content -->
      <div v-else-if="step === 1">
        <div v-if="service" class="mb-4 p-3 bg-bg-primary border border-border rounded-md">
          <p class="font-medium text-sm">{{ service.name }}</p>
          <p class="text-xs text-text-secondary mt-1">{{ service.description || '暂无描述' }}</p>
        </div>
        <h2 class="text-lg font-semibold mb-4">1. 填写内容</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-text-secondary mb-1">任务标题</label>
            <input
              v-model="title"
              type="text"
              class="w-full px-3 py-2 bg-bg-primary border border-border rounded-md text-sm focus:border-accent focus:outline-none"
              placeholder="输入任务标题"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-secondary mb-1">任务描述 (task_prompt)</label>
            <textarea
              v-model="taskPrompt"
              rows="5"
              class="w-full px-3 py-2 bg-bg-primary border border-border rounded-md text-sm focus:border-accent focus:outline-none resize-y"
              placeholder="描述您需要执行的任务..."
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-secondary mb-1">输出要求 (output_prompt)</label>
            <textarea
              v-model="outputPrompt"
              rows="3"
              class="w-full px-3 py-2 bg-bg-primary border border-border rounded-md text-sm focus:border-accent focus:outline-none resize-y"
              placeholder="描述您期望的输出格式..."
            />
          </div>
          <div
            class="border-2 border-dashed rounded-md p-4 text-center transition-colors"
            :class="dragOver ? 'border-accent bg-accent/5' : 'border-border'"
            @dragover.prevent
            @dragenter.prevent="dragOver = true"
            @dragleave.prevent="dragOver = false"
            @drop.prevent="handleDrop"
          >
            <label class="block text-sm font-medium text-text-secondary mb-2">附件 (可选)</label>
            <input
              id="file-input"
              type="file"
              multiple
              class="hidden"
              @change="files = ($event.target as HTMLInputElement).files"
            />
            <label for="file-input" class="cursor-pointer text-sm text-accent hover:underline">
              点击选择文件
            </label>
            <p class="text-xs text-text-muted mt-1">或将文件拖拽到此处</p>
            <p v-if="files && files.length > 0" class="text-xs text-text-secondary mt-2">
              已选择 {{ files.length }} 个文件
            </p>
          </div>
        </div>
        <div class="flex justify-end mt-6">
          <button
            class="px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors"
            @click="nextStep"
          >
            下一步
          </button>
        </div>
      </div>

      <!-- Step 2: Confirm -->
      <div v-if="step === 2">
        <div v-if="service" class="mb-4 p-3 bg-bg-primary border border-border rounded-md">
          <p class="font-medium text-sm">{{ service.name }}</p>
          <p class="text-xs text-text-secondary mt-1">{{ service.description || '暂无描述' }}</p>
        </div>
        <h2 class="text-lg font-semibold mb-4">2. 确认提交</h2>
        <div class="space-y-2 text-sm mb-6">
          <div class="flex">
            <span class="text-text-secondary w-24">服务:</span>
            <span>{{ service?.name || '-' }}</span>
          </div>
          <div class="flex">
            <span class="text-text-secondary w-24">标题:</span>
            <span>{{ title || '未命名任务' }}</span>
          </div>
          <div class="flex">
            <span class="text-text-secondary w-24">文件:</span>
            <span>{{ files?.length || 0 }} 个</span>
          </div>
        </div>
        <div class="flex justify-between">
          <button
            class="px-4 py-2 border border-border rounded-md text-sm font-medium hover:bg-bg-tertiary transition-colors"
            @click="prevStep"
          >
            上一步
          </button>
          <button
            class="px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
            :disabled="taskStore.isSubmitting"
            @click="submit"
          >
            {{ taskStore.isSubmitting ? '提交中...' : '确认提交' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
