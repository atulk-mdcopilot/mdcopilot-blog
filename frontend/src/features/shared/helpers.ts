import { useQuery } from '@tanstack/react-query'
import { sessionQueryOptions } from '@/features/auth/session'
import { hasPermission, type Permission } from '@/features/auth/permissions'
import { ApiError, problemMessage } from '@/lib/api'

export function useCan(permission: Permission) {
  const { data } = useQuery(sessionQueryOptions)
  return hasPermission(data?.user, permission)
}

export function describeProblem(error: unknown, fallback = 'Please try again.') {
  if (error instanceof ApiError && error.body && typeof error.body === 'object' && 'detail' in error.body) {
    const detail = error.body.detail
    return `${problemMessage(error, fallback)}${typeof detail === 'string' ? `: ${detail}` : ''}`
  }
  return error instanceof Error && !(error instanceof ApiError)
    ? error.message
    : problemMessage(error, fallback)
}

export function formatDate(value: string | null, timeZone?: string) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: value.includes('T') ? 'short' : undefined,
    timeZone: value.includes('T') ? timeZone : 'UTC',
  }).format(new Date(value))
}

export function humanLabel(value: string) {
  return value
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replaceAll('_', ' ')
    .replace(/^./, (s) => s.toUpperCase())
}
