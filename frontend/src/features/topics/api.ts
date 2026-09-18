// Topics API
import { apiFetch } from '@/lib/api'
import type { ActionAccepted, ExternalPostOut, Page, TopicHistoryOut, TopicRoundOut } from '@/lib/types'

const TOPICS_QUERY_KEY = ['topics'] as const

export function topicRoundQueryOptions(runId?: string, round?: number) {
  const params = new URLSearchParams()
  if (runId) params.set('runId', runId)
  if (round) params.set('round', String(round))
  return {
    queryKey: [...TOPICS_QUERY_KEY, 'round', runId, round],
    queryFn: () =>
      apiFetch<TopicRoundOut>(`/api/blog-agent/topics${params.size ? `?${params}` : ''}`, { passive: true }),
    staleTime: 5_000,
  }
}

export function topicHistoryQueryOptions(q: string = '', limit: number = 20, offset: number = 0) {
  return {
    queryKey: [...TOPICS_QUERY_KEY, 'history', q, limit, offset],
    queryFn: () =>
      apiFetch<Page<TopicHistoryOut>>(
        `/api/blog-agent/topics/history?limit=${limit}&offset=${offset}${q ? `&q=${encodeURIComponent(q)}` : ''}`,
      ),
    staleTime: 15_000,
  }
}

export function externalPostsQueryOptions(limit: number = 20, offset: number = 0) {
  return {
    queryKey: [...TOPICS_QUERY_KEY, 'external-posts', limit, offset],
    queryFn: () =>
      apiFetch<Page<ExternalPostOut>>(
        `/api/blog-agent/topics/external-posts?limit=${limit}&offset=${offset}`,
        { passive: true },
      ),
    staleTime: 60_000,
  }
}

export function similarTopicsQuery(text: string, limit: number = 5) {
  return apiFetch<{
    text: string
    items: { kind: string; refId: string; title: string; similarity: number }[]
  }>(`/api/blog-agent/topics/similar?text=${encodeURIComponent(text)}&limit=${limit}`)
}

export function generateTopics(runId: string) {
  return apiFetch<ActionAccepted>('/api/blog-agent/topics/generate', {
    method: 'POST',
    json: { runId },
  })
}

export function selectTopic(candidateId: string, confirmWarning: boolean = false) {
  return apiFetch<ActionAccepted>(`/api/blog-agent/topics/${candidateId}/select`, {
    method: 'POST',
    json: { confirmWarning },
  })
}

export function updateTopic(candidateId: string, patch: Record<string, string>) {
  return apiFetch<unknown>(`/api/blog-agent/topics/${candidateId}`, { method: 'PATCH', json: patch })
}

export function rejectTopic(candidateId: string, reason: string) {
  return apiFetch<unknown>(`/api/blog-agent/topics/${candidateId}/reject`, {
    method: 'POST',
    json: { reason },
  })
}
