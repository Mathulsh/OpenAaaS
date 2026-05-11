import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastType = 'success' | 'error' | 'info'

export interface ToastItem {
  id: string
  message: string
  type: ToastType
  createdAt: number
}

export const useUiStore = defineStore('ui', () => {
  const currentTab = ref<string>('home')
  const toastQueue = ref<ToastItem[]>([])
  const sidebarOpen = ref(false)
  const isLoading = ref(false)
  const loadingCount = ref(0)

  function setLoading(value: boolean) {
    loadingCount.value = Math.max(0, loadingCount.value + (value ? 1 : -1))
    isLoading.value = loadingCount.value > 0
  }

  function addToast(message: string, type: ToastType = 'info', duration?: number) {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    toastQueue.value.push({ id, message, type, createdAt: Date.now() })
    setTimeout(() => removeToast(id), Math.max(1000, duration ?? 4000))
  }

  function removeToast(id: string) {
    const idx = toastQueue.value.findIndex((t) => t.id === id)
    if (idx !== -1) {
      toastQueue.value.splice(idx, 1)
    }
  }

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function setSidebarOpen(value: boolean) {
    sidebarOpen.value = value
  }

  function setCurrentTab(tab: string) {
    currentTab.value = tab
  }

  return {
    currentTab,
    toastQueue,
    sidebarOpen,
    isLoading,
    setLoading,
    addToast,
    removeToast,
    toggleSidebar,
    setSidebarOpen,
    setCurrentTab,
  }
})
