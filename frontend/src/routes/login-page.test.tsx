import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { sessionQueryOptions } from '@/features/auth/session'
import { getCsrfToken, setCsrfToken } from '@/lib/api'
import { LoginPage } from '@/routes/login-page'
import { callsTo, jsonResponse, mockApi, problemResponse, renderRoutes, sessionFor } from '@/test/helpers'

function renderLogin(initialEntry = '/login') {
  return renderRoutes(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/', element: <p>home route</p> },
      { path: '/drafts', element: <p>drafts route</p> },
    ],
    { initialEntries: [initialEntry] },
  )
}

async function signIn(email: string, password: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('LoginPage', () => {
  afterEach(() => {
    setCsrfToken(null)
  })

  it('renders the sign-in form', () => {
    renderLogin()

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute('type', 'email')
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
  })

  it('logs in, stores the CSRF token in memory, caches the session and follows ?next=', async () => {
    const session = { ...sessionFor('editor'), csrfToken: 'fresh-token' }
    const fetchMock = mockApi({ 'POST /api/auth/login': () => jsonResponse(session) })
    const { router, queryClient } = renderLogin('/login?next=%2Fdrafts')

    await signIn('editor@example.com', 'correct-horse-battery')

    expect(await screen.findByText('drafts route')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/drafts')
    expect(getCsrfToken()).toBe('fresh-token')
    expect(queryClient.getQueryData(sessionQueryOptions.queryKey)).toEqual(session)
    const [call] = callsTo(fetchMock, 'POST', '/api/auth/login')
    expect(call).toBeDefined()
    expect(JSON.parse(String(call![1]?.body))).toEqual({
      email: 'editor@example.com',
      password: 'correct-horse-battery',
    })
  })

  it.each([
    ['protocol-relative', '%2F%2Fevil.example%2Fx'],
    ['backslash', '%2F%5Cevil.example'],
    ['tab', '%2F%09%2Fevil.example'],
    ['dot segment', '%2F.%2F%2Fevil.example'],
    ['absolute URL', 'https%3A%2F%2Fevil.example%2Fx'],
  ])('ignores an off-site ?next= value (%s)', async (_kind, next) => {
    mockApi({ 'POST /api/auth/login': () => jsonResponse(sessionFor('viewer')) })
    const { router } = renderLogin(`/login?next=${next}`)

    await signIn('viewer@example.com', 'correct-horse-battery')

    expect(await screen.findByText('home route')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('shows an error and stays on the page when the credentials are wrong', async () => {
    mockApi({ 'POST /api/auth/login': () => problemResponse(401, 'Invalid email or password') })
    const { router } = renderLogin()

    await signIn('editor@example.com', 'wrong-password-123')

    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(getCsrfToken()).toBeNull()
  })
})
