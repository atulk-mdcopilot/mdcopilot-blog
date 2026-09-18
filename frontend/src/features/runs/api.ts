import { queryOptions } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'

import type { Page, RunStatus } from '@/lib/types'
export type { RunStatus } from '@/lib/types'

type RunKind = 'daily' | 'manual'

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

const TERMINAL_RUN_STATUSES: ReadonlySet<RunStatus> = new Set<RunStatus>(['SUCCEEDED', 'FAILED', 'CANCELLED'])

export function isTerminalRunStatus(status: RunStatus): boolean {
  return TERMINAL_RUN_STATUSES.has(status)
}

// Prefix shared by every runs query; invalidate it after any run mutation.
const RUNS_QUERY_KEY = ['runs'] as const

const ACTIVE_RUN_POLL_MS = 3_000

export function runsQueryOptions(limit: number, offset = 0) {
  return queryOptions({
    queryKey: [...RUNS_QUERY_KEY, { limit, offset }],
    queryFn: () =>
      apiFetch<Page<RunOut>>(`/api/blog-agent/runs?limit=${limit}${offset ? `&offset=${offset}` : ''}`, {
        passive: true,
      }),
    // Keep polling while any listed run is still moving, so status follows the worker.
    refetchInterval: (query) =>
      query.state.data?.items.some((run) => !isTerminalRunStatus(run.status)) ? ACTIVE_RUN_POLL_MS : false,
  })
}

export function createRun(
  options: {
    topic?: string
    pillar?: string
    audience?: string
    tone?: string
    wordCount?: number
    mode?: string
  } = {},
): Promise<RunOut> {
  return apiFetch<RunOut>('/api/blog-agent/runs', { method: 'POST', json: options })
}

export function cancelRun(runId: string): Promise<RunOut> {
  return apiFetch<RunOut>(`/api/blog-agent/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })
}

export function formatCost(value: string): string {
  const amount = Number(value)
  return Number.isFinite(amount) ? `$${amount.toFixed(4)}` : value
}

type RunDetail = RunOut & {
  params: Record<string, unknown>
  error?: Record<string, unknown> | null
  articleIds?: string[]
  researchRunIds?: string[]
  attempts: {
    id: string
    dbosWorkflowId: string
    workflowName: string
    attemptNo: number
    status: string
    startedAt: string | null
    finishedAt: string | null
    forkedFromWorkflowId: string | null
    error?: Record<string, unknown> | null
  }[]
  steps: {
    id: string
    stepName: string
    dbosStepId: number
    status: string
    tries: number
    agentName: string | null
    model: string | null
    promptName: string | null
    promptVersion: number | null
    inputTokens: number
    outputTokens: number
    costUsd: string
    durationMs: number | null
    error: Record<string, unknown> | null
  }[]
}
export function runDetailQueryOptions(id: string) {
  return queryOptions({
    queryKey: ['runs', id],
    queryFn: () => apiFetch<RunDetail>(`/api/blog-agent/runs/${encodeURIComponent(id)}`, { passive: true }),
    refetchInterval: 3000,
  })
}
export function runAction(
  id: string,
  action: 'restart' | 'resume' | 'retry' | 'restart-step',
  step?: string,
) {
  const suffix = step
    ? `steps/${encodeURIComponent(step)}/${action === 'restart-step' ? 'restart' : action}`
    : action
  return apiFetch<RunOut>(`/api/blog-agent/runs/${encodeURIComponent(id)}/${suffix}`, { method: 'POST' })
}
