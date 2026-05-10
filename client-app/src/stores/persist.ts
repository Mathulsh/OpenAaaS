const STORAGE_KEY = 'openaaas_client_state'

export interface PersistedState {
  servers?: unknown[]
  defaultAlias?: string
  services?: Record<string, unknown>
  tasks?: unknown[]
}

export function loadState(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return JSON.parse(raw) as PersistedState
    }
  } catch {
    // ignore
  }
  return {}
}

export function saveState(partial: Partial<PersistedState>) {
  try {
    const existing = loadState()
    const merged = { ...existing, ...partial }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
  } catch (e) {
    console.warn('Failed to persist state:', e)
  }
}
