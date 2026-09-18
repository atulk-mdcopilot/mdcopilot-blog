import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  cancelRun,
  isTerminalRunStatus,
  runAction,
  runDetailQueryOptions,
  runsQueryOptions,
} from '@/features/runs/api'
import { RunsTable } from '@/features/runs/runs-table'
import { describeProblem, formatDate, useCan } from '@/features/shared/helpers'
import { afterChange } from '@/features/shared/invalidation'
import { PageHeading, Pagination, QueryState, StatusBadge } from '@/features/shared/ui'

function RunDetails({ id }: { id: string }) {
  const client = useQueryClient()
  const canGenerate = useCan('blog.generate')
  const query = useQuery(runDetailQueryOptions(id))
  const data = query.data
  const action = useMutation({
    mutationFn: (perform: () => Promise<unknown>) => perform(),
    onSuccess: async () => {
      toast.success('Run action accepted')
      await afterChange(client)
    },
    onError: (error) => toast.error(describeProblem(error)),
  })
  const terminal = data && isTerminalRunStatus(data.status)

  return (
    <QueryState query={query} label="run detail">
      {data && (
        <div className="space-y-4 rounded-lg border p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold">Run {data.id}</h2>
            <StatusBadge value={data.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            Started {formatDate(data.startedAt)} · ${data.costUsd}
          </p>
          {data.error && (
            <p className="text-sm text-destructive">
              {String(data.error.message ?? data.error.detail ?? 'Generation failed')}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {canGenerate && (
              <>
                {!terminal && (
                  <Button
                    variant="outline"
                    disabled={action.isPending}
                    onClick={() => action.mutate(() => cancelRun(id))}
                  >
                    Cancel run
                  </Button>
                )}
                {terminal && (
                  <Button
                    variant="outline"
                    disabled={action.isPending}
                    onClick={() => {
                      if (window.confirm('Restart this run? This queues a new workflow attempt.'))
                        action.mutate(() => runAction(id, 'restart'))
                    }}
                  >
                    Restart run
                  </Button>
                )}
                <Button
                  variant="outline"
                  disabled={action.isPending}
                  onClick={() => action.mutate(() => runAction(id, 'resume'))}
                >
                  Resume run
                </Button>
              </>
            )}
            {data.articleIds?.map((articleId) => (
              <Button key={articleId} asChild variant="outline">
                <Link to={`/articles/${articleId}`}>Open article</Link>
              </Button>
            ))}
            <Button asChild variant="outline">
              <Link to={`/research?runId=${id}`}>View research</Link>
            </Button>
          </div>
          <h3 className="font-medium">Attempts</h3>
          {data.attempts.map((attempt) => (
            <div key={attempt.id} className="rounded border p-3 text-sm">
              <p>
                Attempt {attempt.attemptNo} · {attempt.workflowName} · {attempt.status}
              </p>
              <p className="text-xs text-muted-foreground">{formatDate(attempt.startedAt)}</p>
              {attempt.error && (
                <p className="text-destructive">
                  {String(attempt.error.message ?? attempt.error.detail ?? 'Workflow failed')}
                </p>
              )}
            </div>
          ))}
          <h3 className="font-medium">Steps</h3>
          {data.steps.map((step) => (
            <div
              key={step.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded border p-3"
            >
              <div>
                <p className="text-sm font-medium">{step.stepName}</p>
                <StatusBadge value={step.status} />
                {step.error && (
                  <p className="mt-1 text-sm text-destructive">
                    {String(step.error.message ?? step.error.detail ?? 'Step failed')}
                  </p>
                )}
              </div>
              {canGenerate && (
                <div className="flex flex-wrap gap-2">
                  {step.status === 'FAILED' && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={action.isPending}
                      onClick={() => action.mutate(() => runAction(id, 'retry', step.stepName))}
                    >
                      Retry step
                    </Button>
                  )}
                  {terminal && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={action.isPending}
                      onClick={() => action.mutate(() => runAction(id, 'restart-step', step.stepName))}
                    >
                      Restart from here
                    </Button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </QueryState>
  )
}

export function RunsPage() {
  const [params, setParams] = useSearchParams()
  const [offset, setOffset] = useState(0)
  const query = useQuery(runsQueryOptions(20, offset))
  const selected = params.get('runId')

  return (
    <section className="space-y-5">
      <PageHeading
        title="Generation runs"
        description="Follow progress and recover interrupted generation."
      />
      <div className="rounded-lg border p-3">
        <RunsTable
          runs={query.data?.items}
          isPending={query.isPending}
          isError={query.isError}
          showRunId
          renderActions={(run) => (
            <Button variant="outline" size="sm" onClick={() => setParams({ runId: run.id })}>
              Details
            </Button>
          )}
        />
      </div>
      <Pagination offset={offset} total={query.data?.total ?? 0} onChange={setOffset} />
      {selected && <RunDetails key={selected} id={selected} />}
    </section>
  )
}
