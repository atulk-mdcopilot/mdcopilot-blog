import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { type RouteObject, RouterProvider, createMemoryRouter } from 'react-router'
import { vi } from 'vitest'
import { Toaster } from '@/components/ui/sonner'
import type { Permission, Role } from '@/features/auth/permissions'
import { type SessionResponse, sessionQueryOptions } from '@/features/auth/session'
import type { Page, RunOut } from '@/features/runs/api'
import { createQueryClient } from '@/lib/query-client'

// Copy of the backend matrix (domain/rbac.py ROLE_PERMISSIONS). The server is the source of truth;
// tests use this copy only to build realistic sessions.
// Names stay camelCase: react-refresh/only-export-components treats any capitalised name in a .tsx
// file as a component and would then flag every exported helper below.
const viewerPermissions: Permission[] = ['blog.view']
const editorPermissions: Permission[] = [...viewerPermissions, 'blog.generate', 'blog.edit']
const reviewerPermissions: Permission[] = [
  ...editorPermissions,
  'blog.review',
  'blog.approve',
  'blog.schedule',
  'blog.agent_runs',
]
const publisherPermissions: Permission[] = [...reviewerPermissions, 'blog.publish']
const adminPermissions: Permission[] = [...publisherPermissions, 'blog.settings']

const rolePermissions: Record<Role, Permission[]> = {
  viewer: viewerPermissions,
  editor: editorPermissions,
  reviewer: reviewerPermissions,
  publisher: publisherPermissions,
  admin: adminPermissions,
}

export function sessionFor(role: Role, permissions: Permission[] = rolePermissions[role]): SessionResponse {
  return {
    user: {
      id: `user-${role}`,
      email: `${role}@example.com`,
      displayName: `Test ${role}`,
      role,
      permissions,
    },
    csrfToken: `csrf-${role}`,
  }
}

export function jsonResponse(body: unknown, status = 200, contentType = 'application/json'): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': contentType } })
}

export function problemResponse(status: number, title: string): Response {
  return jsonResponse({ type: 'about:blank', title, status }, status, 'application/problem+json')
}

export function makeRun(overrides: Partial<RunOut> = {}): RunOut {
  return {
    id: 'run-1',
    kind: 'manual',
    runDate: '2026-09-17',
    status: 'QUEUED',
    stage: null,
    traceId: '0123456789abcdef0123456789abcdef',
    costUsd: '0.000000',
    createdAt: '2026-09-17T07:00:00Z',
    startedAt: null,
    finishedAt: null,
    ...overrides,
  }
}

export function runsPage(items: RunOut[], limit = 10): Page<RunOut> {
  return { items, total: items.length, limit, offset: 0 }
}

type RouteHandler = (init: RequestInit | undefined) => Response

// Stubs global fetch. Keys are "METHOD /path?query"; anything else gets a 404 problem.
// Handlers build a new Response per call because a body can only be read once.
export function mockApi(routes: Record<string, RouteHandler>) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const method = (init?.method ?? 'GET').toUpperCase()
    const handler = routes[`${method} ${String(input)}`]
    return handler ? handler(init) : problemResponse(404, 'Not mocked')
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function callsTo(fetchMock: ReturnType<typeof mockApi>, method: string, path: string) {
  return fetchMock.mock.calls.filter(
    ([input, init]) => String(input) === path && (init?.method ?? 'GET').toUpperCase() === method,
  )
}

type RenderRoutesOptions = {
  initialEntries?: string[]
  session?: SessionResponse
  queryClient?: QueryClient
}

export function renderRoutes(routes: RouteObject[], options: RenderRoutesOptions = {}) {
  const queryClient = options.queryClient ?? createQueryClient()
  if (options.session) {
    queryClient.setQueryData(sessionQueryOptions.queryKey, options.session)
  }
  const router = createMemoryRouter(routes, { initialEntries: options.initialEntries ?? ['/'] })
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>,
  )
  return { router, queryClient, ...view }
}
