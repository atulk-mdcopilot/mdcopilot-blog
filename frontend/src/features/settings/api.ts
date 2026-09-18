// Settings API
import { apiFetch } from '@/lib/api'
import type { PillarOut, SettingsOut } from '@/lib/types'

export function pillarsQueryOptions() {
  return {
    queryKey: ['pillars'],
    queryFn: () => apiFetch<PillarOut[]>('/api/blog-agent/pillars'),
    staleTime: 300_000,
  }
}

const SETTINGS_QUERY_KEY = ['settings'] as const

export function settingsQueryOptions() {
  return {
    queryKey: SETTINGS_QUERY_KEY,
    queryFn: () => apiFetch<SettingsOut>('/api/blog-agent/settings'),
    staleTime: 30_000,
  }
}

export function updateSettings(values: Record<string, unknown>, expectedVersion: number | null) {
  return apiFetch<SettingsOut>('/api/blog-agent/settings', {
    method: 'PUT',
    json: { expectedVersion, values },
  })
}
