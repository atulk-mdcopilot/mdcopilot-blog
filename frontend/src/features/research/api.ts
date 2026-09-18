// Research API
import { apiFetch } from '@/lib/api'
import type { Page, ResearchRunDetail, ResearchRunOut } from '@/lib/types'

const RESEARCH_QUERY_KEY = ['research'] as const

export function researchRunsQueryOptions(
  limit: number = 20,
  offset: number = 0,
  filters: { runId?: string; kind?: string } = {},
) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (filters.runId) params.set('runId', filters.runId)
  if (filters.kind) params.set('kind', filters.kind)
  return {
    queryKey: [...RESEARCH_QUERY_KEY, params.toString()],
    queryFn: () =>
      apiFetch<Page<ResearchRunOut>>(`/api/blog-agent/research-runs?${params}`, { passive: true }),
    staleTime: 10_000,
  }
}

export function researchRunQueryOptions(id: string) {
  return {
    queryKey: [...RESEARCH_QUERY_KEY, 'detail', id],
    queryFn: () => apiFetch<ResearchRunDetail>(`/api/blog-agent/research-runs/${id}`, { passive: true }),
    staleTime: 10_000,
  }
}
