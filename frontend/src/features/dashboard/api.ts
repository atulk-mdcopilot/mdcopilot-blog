// Dashboard API
import { apiFetch } from '@/lib/api'
import type { DashboardOut } from '@/lib/types'

const DASHBOARD_QUERY_KEY = ['dashboard'] as const

export function dashboardQueryOptions() {
  return {
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: () => apiFetch<DashboardOut>('/api/blog-agent/dashboard', { passive: true }),
    staleTime: 10_000,
  }
}
