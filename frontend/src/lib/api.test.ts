import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, getCsrfToken, problemMessage, setCsrfToken } from '@/lib/api'

function jsonResponse(body: unknown, status = 200, contentType = 'application/json'): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': contentType },
  })
}

function mockFetch(response: Response) {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function sentHeaders(fetchMock: ReturnType<typeof mockFetch>): Headers {
  const init = fetchMock.mock.calls[0]?.[1]
  return new Headers(init?.headers)
}

describe('apiFetch', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('sends the in-memory CSRF token on unsafe methods', async () => {
    setCsrfToken('token-from-memory')
    const fetchMock = mockFetch(jsonResponse({ id: 'r1' }, 202))

    const result = await apiFetch<{ id: string }>('/api/blog-agent/runs', {
      method: 'post',
      json: { topic: 'Hello' },
    })

    expect(result).toEqual({ id: 'r1' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/blog-agent/runs')
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('same-origin')
    expect(init?.body).toBe(JSON.stringify({ topic: 'Hello' }))
    const headers = sentHeaders(fetchMock)
    expect(headers.get('X-CSRF-Token')).toBe('token-from-memory')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('does not send the CSRF token on GET', async () => {
    setCsrfToken('token-from-memory')
    const fetchMock = mockFetch(jsonResponse([]))

    await apiFetch('/api/blog-agent/runs')

    expect(sentHeaders(fetchMock).has('X-CSRF-Token')).toBe(false)
  })

  it('omits the header when no token is held and never persists it', async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }))

    await apiFetch('/api/auth/logout', { method: 'POST' })

    expect(getCsrfToken()).toBeNull()
    expect(sentHeaders(fetchMock).has('X-CSRF-Token')).toBe(false)
    expect(window.localStorage.length).toBe(0)
    expect(document.cookie).toBe('')
  })

  it('throws ApiError with status and parsed body on failure', async () => {
    mockFetch(jsonResponse({ detail: 'CSRF token missing' }, 403))

    const error = await apiFetch('/api/blog-agent/runs', { method: 'DELETE' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(403)
    expect((error as ApiError).body).toEqual({ detail: 'CSRF token missing' })
  })

  it('parses application/problem+json error bodies', async () => {
    const problem = { type: 'about:blank', title: 'Agent disabled', status: 409, instance: '/api/blog-agent/runs' }
    mockFetch(jsonResponse(problem, 409, 'application/problem+json'))

    const error = await apiFetch('/api/blog-agent/runs', { method: 'POST', json: {} }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).body).toEqual(problem)
  })
})

describe('problemMessage', () => {
  it('returns the problem title from an ApiError', () => {
    const error = new ApiError(403, { type: 'about:blank', title: 'Forbidden', status: 403 })

    expect(problemMessage(error, 'fallback')).toBe('Forbidden')
  })

  it('falls back for other errors and bodies without a title', () => {
    expect(problemMessage(new ApiError(500, 'Internal Server Error'), 'fallback')).toBe('fallback')
    expect(problemMessage(new TypeError('Failed to fetch'), 'fallback')).toBe('fallback')
  })
})
