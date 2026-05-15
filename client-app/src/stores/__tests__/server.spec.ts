import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useServerStore, type Server, type ServiceItem } from '../server'

vi.mock('@/stores/persist', () => ({
  loadState: vi.fn(() => ({
    servers: [],
    defaultAlias: undefined,
    services: {},
  })),
  saveState: vi.fn(),
}))

vi.mock('@/composables/useHttp', () => ({
  httpFetch: vi.fn(),
  httpFetchWithRedirect: vi.fn(),
  parseServerError: vi.fn(),
}))

import { httpFetch, httpFetchWithRedirect } from '@/composables/useHttp'

const mockedHttpFetch = vi.mocked(httpFetch)
const mockedHttpFetchWithRedirect = vi.mocked(httpFetchWithRedirect)

describe('useServerStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedHttpFetch.mockReset()
    mockedHttpFetchWithRedirect.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('should have empty initial state', () => {
    const store = useServerStore()
    expect(store.servers).toEqual([])
    expect(store.defaultAlias).toBeUndefined()
    expect(store.defaultServer).toBeUndefined()
    expect(store.serverCount).toBe(0)
    expect(store.isFetching).toBe(false)
    expect(store.fetchError).toBeNull()
  })

  it('should add a server and set it as default when first', () => {
    const store = useServerStore()
    const server: Omit<Server, 'isDefault'> = {
      alias: 'local',
      serverUrl: 'http://localhost:8080',
      apiKey: 'key1',
    }
    store.addServer(server)
    expect(store.servers).toHaveLength(1)
    expect(store.servers[0].alias).toBe('local')
    expect(store.servers[0].isDefault).toBe(true)
    expect(store.defaultAlias).toBe('local')
    expect(store.defaultServer?.serverUrl).toBe('http://localhost:8080')
    expect(store.serverCount).toBe(1)
  })

  it('should throw when adding duplicate alias', () => {
    const store = useServerStore()
    store.addServer({ alias: 'local', serverUrl: 'http://localhost:8080' })
    expect(() => store.addServer({ alias: 'local', serverUrl: 'http://localhost:9090' })).toThrow('已存在')
  })

  it('should remove a server and update default', () => {
    const store = useServerStore()
    store.addServer({ alias: 's1', serverUrl: 'http://s1' })
    store.addServer({ alias: 's2', serverUrl: 'http://s2' })
    store.setDefault('s2')
    store.removeServer('s1')
    expect(store.servers).toHaveLength(1)
    expect(store.servers[0].alias).toBe('s2')
    expect(store.servers[0].isDefault).toBe(true)
  })

  it('should update server fields', () => {
    const store = useServerStore()
    store.addServer({ alias: 's1', serverUrl: 'http://s1' })
    store.updateServer('s1', { serverUrl: 'http://s1-new', apiKey: 'new-key' })
    expect(store.servers[0].serverUrl).toBe('http://s1-new')
    expect(store.servers[0].apiKey).toBe('new-key')
  })

  it('should set default server', () => {
    const store = useServerStore()
    store.addServer({ alias: 's1', serverUrl: 'http://s1' })
    store.addServer({ alias: 's2', serverUrl: 'http://s2' })
    store.setDefault('s2')
    expect(store.servers[0].isDefault).toBe(false)
    expect(store.servers[1].isDefault).toBe(true)
    expect(store.defaultAlias).toBe('s2')
  })

  it('should register client and update server', async () => {
    const store = useServerStore()
    store.addServer({ alias: 's1', serverUrl: 'http://s1/' })
    mockedHttpFetchWithRedirect.mockResolvedValue({
      ok: true,
      json: async () => ({ api_key: 'ak', id: 'cid' }),
    } as Response)

    const result = await store.register('s1', 'my-client')
    expect(result.apiKey).toBe('ak')
    expect(result.clientId).toBe('cid')
    expect(store.servers[0].apiKey).toBe('ak')
    expect(store.servers[0].clientId).toBe('cid')
    expect(store.servers[0].clientName).toBe('my-client')
  })

  it('should throw on failed registration', async () => {
    const store = useServerStore()
    store.addServer({ alias: 's1', serverUrl: 'http://s1/' })
    mockedHttpFetchWithRedirect.mockResolvedValue({
      ok: false,
      text: async () => 'bad request',
    } as Response)

    await expect(store.register('s1', 'client')).rejects.toThrow('注册失败')
  })

  it('should fetch services and cache them', async () => {
    const store = useServerStore()
    store.addServer({ alias: 's1', serverUrl: 'http://s1/', apiKey: 'ak' })
    const items: ServiceItem[] = [
      {
        id: 'svc1',
        name: 'Service 1',
        agentStatus: 'online',
        registrationStatus: 'approved',
        accessType: 'public',
        hasPermission: true,
      },
    ]
    mockedHttpFetch.mockResolvedValue({
      ok: true,
      json: async () => items,
    } as Response)

    const result = await store.fetchServices('s1')
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('svc1')
    expect(store.isFetching).toBe(false)
    expect(store.getCachedServices('s1')).toHaveLength(1)
  })

  it('should throw when fetching services without apiKey', async () => {
    const store = useServerStore()
    store.addServer({ alias: 's1', serverUrl: 'http://s1/' })
    await expect(store.fetchServices('s1')).rejects.toThrow('未注册')
  })

  it('should return null for expired cache', () => {
    const store = useServerStore()
    store.addServer({ alias: 's1', serverUrl: 'http://s1/', apiKey: 'ak' })
    store.services['s1'] = {
      fetchedAt: Date.now() - 6 * 60 * 1000,
      items: [],
    }
    expect(store.getCachedServices('s1')).toBeNull()
  })
})
