interface ApiEnvelope<T> {
  data: T
}

interface ErrorPayload {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: Record<string, unknown>

  constructor(
    status: number,
    code: string,
    message: string,
    details?: Record<string, unknown>,
  ) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let csrfToken = ''

export function setCsrfToken(token: string): void {
  csrfToken = token
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (csrfToken && !['GET', 'HEAD', 'OPTIONS'].includes(method)) headers.set('X-CSRF-Token', csrfToken)

  const response = await fetch(path, { credentials: 'same-origin', ...init, headers })
  if (response.status === 204) return undefined as T
  const payload = (await response.json().catch(() => ({}))) as ApiEnvelope<T> & ErrorPayload
  if (!response.ok) {
    throw new ApiError(
      response.status,
      payload.error?.code ?? 'REQUEST_FAILED',
      payload.error?.message ?? `请求失败：${response.status}`,
      payload.error?.details,
    )
  }
  return payload.data
}

export const get = <T>(path: string) => request<T>(path)
export const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
export const patch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
export const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) })
export const remove = (path: string) => request<void>(path, { method: 'DELETE' })

export interface SseEvent {
  event: string
  data: Record<string, unknown>
}

export async function postStream(path: string, body: unknown, onEvent: (event: SseEvent) => void): Promise<void> {
  const headers = new Headers({ Accept: 'text/event-stream', 'Content-Type': 'application/json' })
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers,
    body: JSON.stringify(body),
  })
  if (!response.ok || !response.body) {
    const payload = (await response.json().catch(() => ({}))) as ErrorPayload
    throw new ApiError(response.status, payload.error?.code ?? 'STREAM_FAILED', payload.error?.message ?? '流式请求失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replaceAll('\r\n', '\n')
    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''
    for (const raw of events) {
      const lines = raw.split('\n')
      const dataLine = lines
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('\n')
      if (!dataLine || dataLine === '[DONE]') continue
      try {
        const parsed = JSON.parse(dataLine) as Record<string, unknown>
        const eventLine = lines.find((line) => line.startsWith('event:'))?.slice(6).trim()
        const eventType =
          eventLine ??
          (typeof parsed.event === 'string' ? parsed.event : undefined) ??
          (parsed.error && typeof parsed.error === 'object' ? 'error' : undefined) ??
          'delta'
        onEvent({ event: eventType, data: parsed })
      } catch {
        // skip unparseable lines
      }
    }
  }
}
