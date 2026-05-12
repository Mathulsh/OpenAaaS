import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUiStore } from '../ui'

describe('useUiStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should have default state', () => {
    const store = useUiStore()
    expect(store.currentTab).toBe('home')
    expect(store.sidebarOpen).toBe(false)
    expect(store.isLoading).toBe(false)
    expect(store.toastQueue).toEqual([])
  })

  it('should toggle sidebar', () => {
    const store = useUiStore()
    expect(store.sidebarOpen).toBe(false)
    store.toggleSidebar()
    expect(store.sidebarOpen).toBe(true)
    store.toggleSidebar()
    expect(store.sidebarOpen).toBe(false)
  })

  it('should set sidebar open explicitly', () => {
    const store = useUiStore()
    store.setSidebarOpen(true)
    expect(store.sidebarOpen).toBe(true)
    store.setSidebarOpen(false)
    expect(store.sidebarOpen).toBe(false)
  })

  it('should set current tab', () => {
    const store = useUiStore()
    store.setCurrentTab('settings')
    expect(store.currentTab).toBe('settings')
  })

  it('should track loading count', () => {
    const store = useUiStore()
    store.setLoading(true)
    expect(store.isLoading).toBe(true)
    store.setLoading(true)
    expect(store.isLoading).toBe(true)
    store.setLoading(false)
    expect(store.isLoading).toBe(true)
    store.setLoading(false)
    expect(store.isLoading).toBe(false)
    store.setLoading(false)
    expect(store.isLoading).toBe(false)
  })

  it('should add and remove toast', () => {
    const store = useUiStore()
    store.addToast('hello', 'info')
    expect(store.toastQueue).toHaveLength(1)
    expect(store.toastQueue[0].message).toBe('hello')
    expect(store.toastQueue[0].type).toBe('info')

    const id = store.toastQueue[0].id
    store.removeToast(id)
    expect(store.toastQueue).toHaveLength(0)
  })

  it('should auto-remove toast after timeout', () => {
    const store = useUiStore()
    store.addToast('auto', 'success', 1000)
    expect(store.toastQueue).toHaveLength(1)
    vi.advanceTimersByTime(1100)
    expect(store.toastQueue).toHaveLength(0)
  })
})
