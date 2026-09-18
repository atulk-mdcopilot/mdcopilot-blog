// Quality API
import { apiFetch } from '@/lib/api'
import type { ActionAccepted } from '@/lib/types'

export function approveArticle(
  id: string,
  body: { mode: 'draft' | 'publish'; versionId: string; overrideReason?: string },
) {
  return apiFetch<unknown>(`/api/blog-agent/articles/${id}/approve`, { method: 'POST', json: body })
}

export function rejectArticle(id: string, reason: string) {
  return apiFetch<unknown>(`/api/blog-agent/articles/${id}/reject`, { method: 'POST', json: { reason } })
}

export function recheckArticle(id: string) {
  return apiFetch<ActionAccepted>(`/api/blog-agent/articles/${id}/recheck`, { method: 'POST' })
}
