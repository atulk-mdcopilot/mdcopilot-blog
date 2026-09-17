import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import type { Role } from '@/features/auth/permissions'
import { setCsrfToken } from '@/lib/api'
import { DashboardPage } from '@/routes/dashboard-page'
import {
  callsTo,
  jsonResponse,
  makeRun,
  mockApi,
  problemResponse,
  renderRoutes,
  runsPage,
  sessionFor,
} from '@/test/helpers'

const RUNS_URL = '/api/blog-agent/runs?limit=10'
const GENERATE = "Generate today's blog"

function renderDashboard(role: Role) {
  const session = sessionFor(role)
  // The session loader normally stores the token; these tests seed the cache directly.
  setCsrfToken(session.csrfToken)
  return renderRoutes([{ path: '/', element: <DashboardPage /> }], { session })
}

describe('DashboardPage', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('lists recent runs with status, kind, date and cost', async () => {
    mockApi({
      [`GET ${RUNS_URL}`]: () =>
        jsonResponse(
          runsPage([
            makeRun({ id: 'run-a', status: 'SUCCEEDED', kind: 'daily', runDate: '2026-09-16', costUsd: '0.012300' }),
          ]),
        ),
    })

    renderDashboard('viewer')

    expect(await screen.findByText('SUCCEEDED')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Recent runs' })).toBeInTheDocument()
    expect(screen.getByText('daily')).toBeInTheDocument()
    expect(screen.getByText('2026-09-16')).toBeInTheDocument()
    expect(screen.getByText('$0.0123')).toBeInTheDocument()
  })

  it('hides the generate button from a viewer', async () => {
    mockApi({ [`GET ${RUNS_URL}`]: () => jsonResponse(runsPage([])) })

    renderDashboard('viewer')

    expect(await screen.findByText('No runs yet.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: GENERATE })).not.toBeInTheDocument()
  })

  it('starts a run with the CSRF header and refreshes the list', async () => {
    const fetchMock = mockApi({
      [`GET ${RUNS_URL}`]: () => jsonResponse(runsPage([])),
      'POST /api/blog-agent/runs': () => jsonResponse(makeRun({ id: 'run-new' }), 202),
    })
    const user = userEvent.setup()
    renderDashboard('editor')
    await screen.findByText('No runs yet.')

    await user.click(screen.getByRole('button', { name: GENERATE }))

    expect(await screen.findByText('Run queued')).toBeInTheDocument()
    const posts = callsTo(fetchMock, 'POST', '/api/blog-agent/runs')
    expect(posts).toHaveLength(1)
    const init = posts[0]![1]
    expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('csrf-editor')
    expect(init?.body).toBe('{}')
    await waitFor(() => expect(callsTo(fetchMock, 'GET', RUNS_URL)).toHaveLength(2))
  })

  it('shows the problem title when the API refuses the run', async () => {
    mockApi({
      [`GET ${RUNS_URL}`]: () => jsonResponse(runsPage([])),
      'POST /api/blog-agent/runs': () => problemResponse(409, 'Agent disabled'),
    })
    const user = userEvent.setup()
    renderDashboard('admin')
    await screen.findByText('No runs yet.')

    await user.click(screen.getByRole('button', { name: GENERATE }))

    expect(await screen.findByText('Agent disabled')).toBeInTheDocument()
  })

  it('says so when the runs cannot be loaded', async () => {
    mockApi({ [`GET ${RUNS_URL}`]: () => problemResponse(403, 'Forbidden') })

    renderDashboard('viewer')

    expect(await screen.findByText('Could not load runs.')).toBeInTheDocument()
  })
})
