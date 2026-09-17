import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { NAV_ITEMS } from '@/app/nav'
import type { SessionResponse } from '@/features/auth/session'
import { getCsrfToken, setCsrfToken } from '@/lib/api'
import { createQueryClient } from '@/lib/query-client'
import { buildRoutes } from '@/router'
import {
  callsTo,
  jsonResponse,
  mockApi,
  problemResponse,
  renderRoutes,
  runsPage,
  sessionFor,
} from '@/test/helpers'

function mockBackend(session: SessionResponse | null) {
  return mockApi({
    'GET /api/auth/session': () =>
      session ? jsonResponse(session) : problemResponse(401, 'Not authenticated'),
    'POST /api/auth/logout': () => new Response(null, { status: 204 }),
    'GET /api/blog-agent/runs?limit=10': () => jsonResponse(runsPage([])),
    'GET /api/blog-agent/runs?limit=50': () => jsonResponse(runsPage([], 50)),
  })
}

function renderApp(path: string) {
  const queryClient = createQueryClient()
  return renderRoutes(buildRoutes(queryClient), { initialEntries: [path], queryClient })
}

async function go(router: ReturnType<typeof renderApp>['router'], path: string) {
  await act(async () => {
    await router.navigate(path)
  })
}

describe('router', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('sends a visitor without a session to /login and keeps the requested path in ?next=', async () => {
    mockBackend(null)

    const { router } = renderApp('/drafts?tab=1')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toBe('?next=%2Fdrafts%3Ftab%3D1')
  })

  it('renders every nav page for an admin', async () => {
    const fetchMock = mockBackend(sessionFor('admin'))

    const { router } = renderApp('/')

    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
    expect(getCsrfToken()).toBe('csrf-admin')
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getAllByRole('link')).toHaveLength(NAV_ITEMS.length)

    for (const item of NAV_ITEMS.filter((navItem) => navItem.path !== '/')) {
      await go(router, item.path)
      expect(await screen.findByRole('heading', { level: 1, name: item.label })).toBeInTheDocument()
      if (item.path !== '/agent-runs') {
        expect(screen.getByText('Arrives in a later phase.')).toBeInTheDocument()
      }
    }
    expect(callsTo(fetchMock, 'GET', '/api/auth/session')).toHaveLength(1)
  })

  it('shows Access denied when a viewer opens a page outside their role', async () => {
    mockBackend(sessionFor('viewer'))

    const { router } = renderApp('/settings')

    expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getAllByRole('link')).toHaveLength(8)
    expect(within(nav).queryByRole('link', { name: 'Settings' })).not.toBeInTheDocument()

    for (const path of ['/review', '/agent-runs']) {
      await go(router, path)
      expect(await screen.findByRole('heading', { name: 'Access denied' })).toBeInTheDocument()
    }

    await go(router, '/topics')
    expect(await screen.findByRole('heading', { level: 1, name: 'Topics' })).toBeInTheDocument()
  })

  it('redirects unknown paths to the dashboard', async () => {
    mockBackend(sessionFor('viewer'))

    const { router } = renderApp('/no-such-page')

    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('signs out from the user menu with the CSRF token and returns to /login', async () => {
    const fetchMock = mockBackend(sessionFor('editor'))
    const user = userEvent.setup()
    const { router } = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Test editor' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    const posts = callsTo(fetchMock, 'POST', '/api/auth/logout')
    expect(posts).toHaveLength(1)
    expect(new Headers(posts[0]![1]?.headers).get('X-CSRF-Token')).toBe('csrf-editor')
    expect(getCsrfToken()).toBeNull()
  })
})
