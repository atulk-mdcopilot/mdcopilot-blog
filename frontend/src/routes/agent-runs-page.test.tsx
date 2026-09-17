import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import type { SessionResponse } from '@/features/auth/session'
import { setCsrfToken } from '@/lib/api'
import { AgentRunsPage } from '@/routes/agent-runs-page'
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

const RUNS_URL = '/api/blog-agent/runs?limit=50'
const CANCEL_URL = '/api/blog-agent/runs/run-active/cancel'

function renderAgentRuns(session: SessionResponse) {
  setCsrfToken(session.csrfToken)
  return renderRoutes([{ path: '/agent-runs', element: <AgentRunsPage /> }], {
    initialEntries: ['/agent-runs'],
    session,
  })
}

const activeAndFinished = () =>
  jsonResponse(
    runsPage(
      [makeRun({ id: 'run-active', status: 'PRODUCING' }), makeRun({ id: 'run-done', status: 'SUCCEEDED' })],
      50,
    ),
  )

describe('AgentRunsPage', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('offers Cancel only for runs that are still moving and cancels with the CSRF header', async () => {
    const fetchMock = mockApi({
      [`GET ${RUNS_URL}`]: activeAndFinished,
      [`POST ${CANCEL_URL}`]: () => jsonResponse(makeRun({ id: 'run-active', status: 'CANCELLED' }), 202),
    })
    const user = userEvent.setup()
    renderAgentRuns(sessionFor('reviewer'))

    const cancel = await screen.findByRole('button', { name: 'Cancel run run-active' })
    expect(screen.getByRole('heading', { name: 'Agent Runs' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel run run-done' })).not.toBeInTheDocument()

    await user.click(cancel)

    expect(await screen.findByText('Run cancelled')).toBeInTheDocument()
    const posts = callsTo(fetchMock, 'POST', CANCEL_URL)
    expect(posts).toHaveLength(1)
    expect(new Headers(posts[0]![1]?.headers).get('X-CSRF-Token')).toBe('csrf-reviewer')
    await waitFor(() => expect(callsTo(fetchMock, 'GET', RUNS_URL).length).toBeGreaterThanOrEqual(2))
  })

  it('shows the problem title when the run can no longer be cancelled', async () => {
    mockApi({
      [`GET ${RUNS_URL}`]: activeAndFinished,
      [`POST ${CANCEL_URL}`]: () => problemResponse(409, 'Run cannot be cancelled'),
    })
    const user = userEvent.setup()
    renderAgentRuns(sessionFor('admin'))

    await user.click(await screen.findByRole('button', { name: 'Cancel run run-active' }))

    expect(await screen.findByText('Run cannot be cancelled')).toBeInTheDocument()
  })

  it('hides Cancel from a user without blog.generate', async () => {
    mockApi({ [`GET ${RUNS_URL}`]: activeAndFinished })

    renderAgentRuns(sessionFor('viewer', ['blog.view', 'blog.agent_runs']))

    expect(await screen.findByText('PRODUCING')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Cancel run/ })).not.toBeInTheDocument()
  })
})
