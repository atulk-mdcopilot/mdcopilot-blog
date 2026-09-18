// Sources API
import { apiFetch } from '@/lib/api'
import type { LedgerSourceOut, Page, SourceDomainOut, SourceFeedOut, ThemeOut } from '@/lib/types'

const SOURCES_QUERY_KEY = ['sources'] as const

export function sourcesQueryOptions(
  limit: number = 20,
  offset: number = 0,
  filters: { domain?: string; tier?: number; q?: string; accessMode?: string } = {},
) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (filters.domain) params.set('domain', filters.domain)
  if (filters.tier !== undefined) params.set('tier', String(filters.tier))
  if (filters.q) params.set('q', filters.q)
  if (filters.accessMode) params.set('accessMode', filters.accessMode)
  return {
    queryKey: [...SOURCES_QUERY_KEY, params.toString()],
    queryFn: () => apiFetch<Page<LedgerSourceOut>>(`/api/blog-agent/sources?${params}`),
    staleTime: 15_000,
  }
}

export function feedsQueryOptions() {
  return {
    queryKey: [...SOURCES_QUERY_KEY, 'feeds'],
    queryFn: () => apiFetch<SourceFeedOut[]>('/api/blog-agent/sources/feeds'),
    staleTime: 30_000,
  }
}

export function domainsQueryOptions() {
  return {
    queryKey: [...SOURCES_QUERY_KEY, 'domains'],
    queryFn: () => apiFetch<SourceDomainOut[]>('/api/blog-agent/sources/domains'),
    staleTime: 30_000,
  }
}

export function themesQueryOptions() {
  return {
    queryKey: [...SOURCES_QUERY_KEY, 'themes'],
    queryFn: () => apiFetch<ThemeOut[]>('/api/blog-agent/themes'),
    staleTime: 30_000,
  }
}

export function updateFeed(id: string, patch: Record<string, unknown>) {
  return apiFetch<SourceFeedOut>(`/api/blog-agent/sources/feeds/${id}`, { method: 'PATCH', json: patch })
}

export function updateDomain(id: string, patch: Record<string, unknown>) {
  return apiFetch<SourceDomainOut>(`/api/blog-agent/sources/domains/${id}`, { method: 'PATCH', json: patch })
}

export function updateThemes(items: unknown[]) {
  return apiFetch<ThemeOut[]>('/api/blog-agent/themes', { method: 'PUT', json: { items } })
}
