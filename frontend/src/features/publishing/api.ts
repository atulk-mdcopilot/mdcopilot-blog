import { queryOptions } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'
import { articlePath } from '@/features/articles/api'
import type { ActionAccepted, ExportBundleOut, PreviewOut, PublicationOut } from '@/lib/types'
export function previewQueryOptions(id: string, versionId?: string) {
  return queryOptions({
    queryKey: ['articles', id, 'preview', versionId],
    queryFn: () =>
      apiFetch<PreviewOut>(
        articlePath(id, `/preview${versionId ? `?versionId=${encodeURIComponent(versionId)}` : ''}`),
      ),
  })
}
export function publicationsQueryOptions(id: string) {
  return queryOptions({
    queryKey: ['articles', id, 'publications'],
    queryFn: () => apiFetch<PublicationOut[]>(articlePath(id, '/publications')),
  })
}
export function exportArticle(id: string) {
  return apiFetch<ExportBundleOut>(articlePath(id, '/export'), { method: 'POST' })
}
export function publishArticle(id: string, asDraft?: boolean) {
  return apiFetch<ActionAccepted>(articlePath(id, '/publish'), {
    method: 'POST',
    json: asDraft === undefined ? {} : { asDraft },
  })
}
export function confirmPublished(id: string, url: string) {
  return apiFetch<unknown>(articlePath(id, '/confirm-published'), { method: 'POST', json: { url } })
}
export function scheduleArticle(id: string, at: string) {
  return apiFetch<unknown>(articlePath(id, '/schedule'), { method: 'POST', json: { at } })
}
export function unscheduleArticle(id: string) {
  return apiFetch<unknown>(articlePath(id, '/unschedule'), { method: 'POST' })
}
