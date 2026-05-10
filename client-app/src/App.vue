<script setup lang="ts">
import { onMounted } from 'vue'
import { useTaskStore } from '@/stores/task'
import SideNav from '@/components/SideNav.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import LoadingBar from '@/components/LoadingBar.vue'

const taskStore = useTaskStore()


onMounted(() => {
  // Resume polling for active tasks on app start
  taskStore.resumePolling()
})
</script>

<template>
  <div class="flex h-screen w-screen bg-bg-primary text-text-primary">
    <LoadingBar />
    <SideNav />
    <main class="flex-1 flex flex-col min-w-0 relative overflow-hidden">
      <div class="flex-1 overflow-y-auto p-6">
        <router-view />
      </div>
    </main>
    <ToastContainer />
  </div>
</template>
