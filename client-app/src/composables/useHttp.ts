import { fetch as tauriFetch } from '@tauri-apps/plugin-http'

/**
 * Use Tauri HTTP plugin fetch to bypass browser CORS restrictions.
 * Falls back to native fetch if not in Tauri environment.
 */
export async function httpFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    // Attempt to use Tauri plugin fetch (bypasses CORS)
    return await tauriFetch(input, init)
  } catch {
    // Fallback to native fetch (for dev server outside Tauri)
    return fetch(input, init)
  }
}

/**
 * Fetch with manual redirect handling to preserve HTTP method on 3xx redirects.
 * Prevents POST→GET conversion on 301/302 and strips Authorization on cross-domain redirects.
 */
export async function httpFetchWithRedirect(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  let currentUrl: string = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
  let remainingRedirects = 3
  const originalHost = new URL(currentUrl).host

  // Deep clone init for loop mutation
  let workingInit = init ? { ...init } : undefined
  if (workingInit?.headers) {
    workingInit = { ...workingInit, headers: new Headers(workingInit.headers) }
  }

  while (remainingRedirects >= 0) {
    try {
      const response = await tauriFetch(currentUrl, { ...workingInit, redirect: 'manual' })

      if (response.status >= 300 && response.status < 400) {
        const location = response.headers.get('Location')
        if (location) {
          if (remainingRedirects > 0) {
            currentUrl = new URL(location, currentUrl).toString()
            remainingRedirects--

            // Strip Authorization on cross-domain redirect
            if (workingInit?.headers) {
              const currentHost = new URL(currentUrl).host
              if (currentHost !== originalHost) {
                ;(workingInit.headers as Headers).delete('Authorization')
              }
            }
            continue
          }
          throw new Error('请求被多次重定向，请直接使用 HTTPS URL')
        }
      }
      return response
    } catch (err) {
      // If it's our own "too many redirects" error, re-throw it
      if (err instanceof Error && err.message === '请求被多次重定向，请直接使用 HTTPS URL') {
        throw err
      }
      // tauriFetch doesn't support manual redirect, fall back to normal httpFetch
      return httpFetch(input, init)
    }
  }
}

/**
 * Upload files using multipart/form-data constructed as Uint8Array.
 * Browser FormData with File objects cannot be serialized over Tauri IPC.
 */
export async function uploadWithFiles(
  url: string,
  fields: Record<string, string>,
  files: File[],
  headers?: Record<string, string>,
): Promise<Response> {
  const boundary = '----TauriFormBoundary' + Math.random().toString(36).slice(2)
  const encoder = new TextEncoder()
  const parts: Uint8Array[] = []

  for (const [key, value] of Object.entries(fields)) {
    parts.push(encoder.encode(`--${boundary}\r\n`))
    parts.push(encoder.encode(`Content-Disposition: form-data; name="${key}"\r\n\r\n`))
    parts.push(encoder.encode(`${value}\r\n`))
  }

  for (const file of files) {
    const buffer = await file.arrayBuffer()
    const safeName = file.name.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r/g, '').replace(/\n/g, '')
    parts.push(encoder.encode(`--${boundary}\r\n`))
    parts.push(encoder.encode(`Content-Disposition: form-data; name="files"; filename="${safeName}"\r\n`))
    parts.push(encoder.encode(`Content-Type: ${file.type || 'application/octet-stream'}\r\n\r\n`))
    parts.push(new Uint8Array(buffer))
    parts.push(encoder.encode(`\r\n`))
  }

  parts.push(encoder.encode(`--${boundary}--\r\n`))

  let totalLength = 0
  for (const p of parts) totalLength += p.length
  const body = new Uint8Array(totalLength)
  let offset = 0
  for (const p of parts) {
    body.set(p, offset)
    offset += p.length
  }

  return httpFetchWithRedirect(url, {
    method: 'POST',
    headers: {
      ...(headers || {}),
      'Content-Type': `multipart/form-data; boundary=${boundary}`,
    },
    body,
  })
}
