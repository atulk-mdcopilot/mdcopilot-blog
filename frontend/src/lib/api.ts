// Thin fetch wrapper for the FastAPI backend.
// The CSRF token lives only in module memory: never in localStorage, never in a JS-readable cookie.

let csrfToken: string | null = null

export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

export function getCsrfToken(): string | null {
  return csrfToken
}

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export type ApiRequestInit = Omit<RequestInit, 'body'> & {
  body?: BodyInit | null
  json?: unknown
}

// The backend sends errors as application/problem+json, so accept any JSON media type.
function isJsonContentType(value: string | null): boolean {
  if (value === null) {
    return false
  }
  const mediaType = value.split(';')[0].trim().toLowerCase()
  return mediaType === 'application/json' || mediaType.endsWith('+json')
}

export async function apiFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { json, headers: initHeaders, body: initBody, method: initMethod, ...rest } = init
  const method = (initMethod ?? 'GET').toUpperCase()
  const headers = new Headers(initHeaders)
  headers.set('Accept', 'application/json')

  let body = initBody
  if (json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(json)
  }

  if (UNSAFE_METHODS.has(method) && csrfToken !== null) {
    headers.set('X-CSRF-Token', csrfToken)
  }

  const response = await fetch(path, {
    ...rest,
    method,
    headers,
    body,
    credentials: 'same-origin',
  })

  const text = await response.text()
  const isJson = isJsonContentType(response.headers.get('Content-Type'))
  const data: unknown = text && isJson ? JSON.parse(text) : text || undefined

  if (!response.ok) {
    throw new ApiError(response.status, data)
  }
  return data as T
}

// Human-readable message for a failed request: the problem+json title when there is one.
export function problemMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const body = error.body
    if (typeof body === 'object' && body !== null && 'title' in body && typeof body.title === 'string') {
      return body.title
    }
  }
  return fallback
}
