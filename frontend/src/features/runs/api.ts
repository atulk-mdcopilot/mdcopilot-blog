import { queryOptions } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'

// Mirrors backend domain/enums.py RunStatus and RunKind.
export type RunStatus =
  | 'QUEUED'
  | 'RESEARCHING'
  | 'TOPICS_READY'
  | 'WAITING_FOR_TOPIC'
  | 'PRODUCING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED'

export type RunKind = 'daily' | 'manual'

// Mirrors backend api/schemas.py RunOut (camelCase JSON). Pydantic sends Decimal as a string.
export type RunOut = {
  id: string
  kind: RunKind
  runDate: string
  status: RunStatus
  stage: string | null
  traceId: string
  costUsd: string
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
}

export type Page<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}

const TERMINAL_RUN_STATUSES: ReadonlySet<RunStatus> = new Set<RunStatus>(['SUCCEEDED', 'FAILED', 'CANCELLED'])

export function isTerminalRunStatus(status: RunStatus): boolean {
  return TERMINAL_RUN_STATUSES.has(status)
}

// Prefix shared by every runs query; invalidate it after any run mutation.
export const RUNS_QUERY_KEY = ['runs'] as const

const ACTIVE_RUN_POLL_MS = 3_000

export function runsQueryOptions(limit: number) {
  return queryOptions({
    queryKey: [...RUNS_QUERY_KEY, { limit }],
    queryFn: () => apiFetch<Page<RunOut>>(`/api/blog-agent/runs?limit=${limit}`),
    // Keep polling while any listed run is still moving, so status follows the worker.
    refetchInterval: (query) =>
      query.state.data?.items.some((run) => !isTerminalRunStatus(run.status)) ? ACTIVE_RUN_POLL_MS : false,
  })
}

export function createRun(): Promise<RunOut> {
  return apiFetch<RunOut>('/api/blog-agent/runs', { method: 'POST', json: {} })
}

export function cancelRun(runId: string): Promise<RunOut> {
  return apiFetch<RunOut>(`/api/blog-agent/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })
}

export function formatCost(value: string): string {
  const amount = Number(value)
  return Number.isFinite(amount) ? `$${amount.toFixed(4)}` : value
}
