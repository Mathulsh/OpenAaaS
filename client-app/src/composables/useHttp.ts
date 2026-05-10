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

  return httpFetch(url, {
    method: 'POST',
    headers: {
      ...(headers || {}),
      'Content-Type': `multipart/form-data; boundary=${boundary}`,
    },
    body,
  })
}
