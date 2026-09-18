import { queryOptions } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'
import type {
  ActionAccepted,
  ArticleDetailOut,
  ArticleEdit,
  ArticleSourceOut,
  ArticleSummaryOut,
  Page,
  ResearchPacketOut,
  VersionDetailOut,
  VersionDiffOut,
  VersionSummaryOut,
} from '@/lib/types'
export function articlePath(id: string, suffix = '') {
  return `/api/blog-agent/articles/${encodeURIComponent(id)}${suffix}`
}
const movingArticle = (status: string) =>
  ['DRAFTING', 'FACT_CHECKING', 'CLINICAL_REVIEW', 'EDITORIAL_REVIEW', 'SEO', 'PUBLISHING'].includes(status)
export function articlesQueryOptions(
  view: 'drafts' | 'review' | 'published' | 'all' = 'all',
  limit = 20,
  offset = 0,
  filters: { pillar?: string; q?: string } = {},
) {
  const params = new URLSearchParams({ view, limit: String(limit), offset: String(offset), ...filters })
  return queryOptions({
    queryKey: ['articles', 'list', params.toString()],
    queryFn: () => apiFetch<Page<ArticleSummaryOut>>(`/api/blog-agent/articles?${params}`, { passive: true }),
    refetchInterval: (q) => (q.state.data?.items.some((a) => movingArticle(a.status)) ? 3000 : 15000),
  })
}
export function articleQueryOptions(id: string) {
  return queryOptions({
    queryKey: ['articles', id, 'detail'],
    queryFn: () => apiFetch<ArticleDetailOut>(articlePath(id), { passive: true }),
    refetchInterval: (q) => (q.state.data && movingArticle(q.state.data.status) ? 3000 : 10000),
  })
}
export function articleSourcesQueryOptions(id: string) {
  return queryOptions({
    queryKey: ['articles', id, 'sources'],
    queryFn: () => apiFetch<ArticleSourceOut[]>(articlePath(id, '/sources')),
  })
}
export function packetsQueryOptions(id: string) {
  return queryOptions({
    queryKey: ['articles', id, 'research-packets'],
    queryFn: () => apiFetch<ResearchPacketOut[]>(articlePath(id, '/research-packets')),
  })
}
export function versionsQueryOptions(id: string) {
  return queryOptions({
    queryKey: ['articles', id, 'versions'],
    queryFn: () => apiFetch<VersionSummaryOut[]>(articlePath(id, '/versions')),
  })
}
export function versionQueryOptions(id: string, version: string) {
  return queryOptions({
    queryKey: ['articles', id, 'version', version],
    queryFn: () => apiFetch<VersionDetailOut>(articlePath(id, `/versions/${encodeURIComponent(version)}`)),
    enabled: !!version,
  })
}
export function diffQueryOptions(id: string, from: string, to: string) {
  return queryOptions({
    queryKey: ['articles', id, 'diff', from, to],
    queryFn: () => apiFetch<VersionDiffOut>(articlePath(id, `/diff?${new URLSearchParams({ from, to })}`)),
    enabled: !!from && !!to && from !== to,
  })
}
export function editArticle(id: string, body: ArticleEdit) {
  return apiFetch<ArticleDetailOut>(articlePath(id), { method: 'PATCH', json: body })
}
export function selectTitle(id: string, body: { key: string } | { customTitle: string }) {
  return apiFetch<ArticleDetailOut>(articlePath(id, '/select-title'), { method: 'POST', json: body })
}
export function regenerateArticle(
  id: string,
  body: { component: string; sectionKey?: string; instructions?: string },
) {
  return apiFetch<ActionAccepted>(articlePath(id, '/regenerate'), { method: 'POST', json: body })
}
