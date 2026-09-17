import { queryOptions } from '@tanstack/react-query'
import type { Permission, Role } from '@/features/auth/permissions'
import { apiFetch, setCsrfToken } from '@/lib/api'

// Mirrors backend api/schemas.py SessionUser / SessionResponse (camelCase JSON).
export type SessionUser = {
  id: string
  email: string
  displayName: string
  role: Role
  permissions: Permission[]
}

export type SessionResponse = {
  user: SessionUser
  csrfToken: string
}

export type LoginInput = {
  email: string
  password: string
}

export const sessionQueryOptions = queryOptions({
  queryKey: ['session'],
  queryFn: async () => {
    const session = await apiFetch<SessionResponse>('/api/auth/session')
    setCsrfToken(session.csrfToken)
    return session
  },
  staleTime: 60_000,
  retry: false,
})

export async function login(input: LoginInput): Promise<SessionResponse> {
  const session = await apiFetch<SessionResponse>('/api/auth/login', {
    method: 'POST',
    json: input,
  })
  setCsrfToken(session.csrfToken)
  return session
}

export async function logout(): Promise<void> {
  try {
    await apiFetch<void>('/api/auth/logout', { method: 'POST' })
  } finally {
    setCsrfToken(null)
  }
}
