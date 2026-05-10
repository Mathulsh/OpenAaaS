<script setup lang="ts">
import { ref } from 'vue'
import { useServerStore } from '@/stores/server'
import { useUiStore } from '@/stores/ui'

const serverStore = useServerStore()
const uiStore = useUiStore()

const showAddForm = ref(false)
const newAlias = ref('')
const newUrl = ref('')
const registerAlias = ref('')
const registerName = ref('')
const showRegisterForm = ref(false)

function addServer() {
  if (!newAlias.value.trim()) {
    uiStore.addToast('别名不能为空', 'error')
    return
  }
  if (!newUrl.value.trim()) {
    uiStore.addToast('服务器地址不能为空', 'error')
    return
  }
  if (!/^https?:\/\//i.test(newUrl.value)) {
    uiStore.addToast('服务器地址必须以 http:// 或 https:// 开头', 'error')
    return
  }
  try {
    new URL(newUrl.value.trim())
  } catch {
    uiStore.addToast('服务器地址格式不正确', 'error')
    return
  }
  try {
    serverStore.addServer({
      alias: newAlias.value.trim(),
      serverUrl: newUrl.value.trim(),
    })
    uiStore.addToast('服务器添加成功', 'success')
    newAlias.value = ''
    newUrl.value = ''
    showAddForm.value = false
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    uiStore.addToast(msg, 'error')
  }
}

async function doRegister() {
  if (!registerName.value.trim()) {
    uiStore.addToast('用户名不能为空', 'error')
    return
  }
  try {
    uiStore.setLoading(true)
    await serverStore.register(registerAlias.value, registerName.value.trim())
    uiStore.addToast('注册成功', 'success')
    showRegisterForm.value = false
    registerName.value = ''
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    uiStore.addToast(msg, 'error')
  } finally {
    uiStore.setLoading(false)
  }
}

function openRegister(alias: string) {
  registerAlias.value = alias
  showRegisterForm.value = true
}

function closeRegister() {
  showRegisterForm.value = false
  registerName.value = ''
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h1 class="text-2xl font-bold mb-6">设置</h1>

    <!-- Server List -->
    <div class="bg-bg-secondary border border-border rounded-lg p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold">服务器管理</h2>
        <button
          class="px-3 py-1.5 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors"
          @click="showAddForm = !showAddForm"
        >
          {{ showAddForm ? '取消' : '添加服务器' }}
        </button>
      </div>

      <!-- Add form -->
      <div v-if="showAddForm" class="bg-bg-primary border border-border rounded-md p-4 mb-4">
        <div class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-text-secondary mb-1">别名 *</label>
            <input
              v-model="newAlias"
              type="text"
              class="w-full px-3 py-2 bg-bg-secondary border border-border rounded-md text-sm focus:border-accent focus:outline-none"
              placeholder="如 prod, local"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-secondary mb-1">服务器地址 *</label>
            <input
              v-model="newUrl"
              type="text"
              class="w-full px-3 py-2 bg-bg-secondary border border-border rounded-md text-sm focus:border-accent focus:outline-none"
              placeholder="https://api.open-aaas.com"
            />
            <p class="text-xs text-text-muted mt-1">必须以 http:// 或 https:// 开头</p>
          </div>
          <div class="flex gap-2">
            <button
              class="px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors"
              @click="addServer"
            >
              确认添加
            </button>
            <button
              class="px-4 py-2 border border-border rounded-md text-sm font-medium hover:bg-bg-tertiary transition-colors"
              @click="showAddForm = false"
            >
              取消
            </button>
          </div>
        </div>
      </div>

      <!-- Register form -->
      <div v-if="showRegisterForm" class="bg-bg-primary border border-border rounded-md p-4 mb-4">
        <p class="text-sm text-text-secondary mb-3">
          注册客户端到服务器: <strong>{{ registerAlias }}</strong>
        </p>
        <div class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-text-secondary mb-1">用户名 *</label>
            <input
              v-model="registerName"
              type="text"
              class="w-full px-3 py-2 bg-bg-secondary border border-border rounded-md text-sm focus:border-accent focus:outline-none"
              placeholder="输入用户名"
            />
            <p class="text-xs text-text-muted mt-1">长度不超过64字符，不含特殊字符</p>
          </div>
          <div class="flex gap-2">
            <button
              class="px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors"
              @click="doRegister"
            >
              注册
            </button>
            <button
              class="px-4 py-2 border border-border rounded-md text-sm font-medium hover:bg-bg-tertiary transition-colors"
              @click="closeRegister"
            >
              返回
            </button>
          </div>
        </div>
      </div>

      <!-- Server list -->
      <div v-if="serverStore.servers.length === 0" class="text-center py-8 text-text-muted">
        <p>暂无服务器配置</p>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="server in serverStore.servers"
          :key="server.alias"
          class="bg-bg-primary border rounded-md p-3 flex items-center gap-3 flex-wrap"
          :class="server.isDefault ? 'border-accent bg-accent/5' : 'border-border'"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-semibold text-sm">{{ server.alias }}</span>
              <span
                v-if="server.isDefault"
                class="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-accent/10 text-accent"
              >
                默认
              </span>
              <span
                v-if="server.apiKey"
                class="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-success/10 text-success"
              >
                已注册
              </span>
              <span
                v-else
                class="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-danger/10 text-danger"
              >
                未注册
              </span>
            </div>
            <p class="text-xs text-text-muted truncate">{{ server.serverUrl }}</p>
          </div>

          <div class="flex gap-2">
            <button
              v-if="!server.isDefault"
              class="px-2 py-1 text-xs border border-border rounded hover:bg-bg-tertiary transition-colors"
              @click="serverStore.setDefault(server.alias)"
            >
              设为默认
            </button>
            <button
              v-if="!server.apiKey"
              class="px-2 py-1 text-xs bg-accent text-white rounded hover:bg-accent-hover transition-colors"
              @click="openRegister(server.alias)"
            >
              注册
            </button>
            <button
              v-if="!server.isDefault"
              class="px-2 py-1 text-xs bg-danger text-white rounded hover:opacity-90 transition-opacity"
              @click="serverStore.removeServer(server.alias)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
