import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { hasPermission } from '@/features/auth/permissions'
import { sessionQueryOptions } from '@/features/auth/session'
import {
  RUNS_QUERY_KEY,
  type RunOut,
  cancelRun,
  isTerminalRunStatus,
  runsQueryOptions,
} from '@/features/runs/api'
import { RunsTable } from '@/features/runs/runs-table'
import { problemMessage } from '@/lib/api'

const AGENT_RUNS_LIMIT = 50

export function AgentRunsPage() {
  const queryClient = useQueryClient()
  const { data: session } = useQuery(sessionQueryOptions)
  const runs = useQuery(runsQueryOptions(AGENT_RUNS_LIMIT))
  const canCancel = hasPermission(session?.user, 'blog.generate')

  const cancel = useMutation({
    mutationFn: cancelRun,
    onSuccess: async () => {
      toast.success('Run cancelled')
      await queryClient.invalidateQueries({ queryKey: RUNS_QUERY_KEY })
    },
    onError: (error) => {
      toast.error(problemMessage(error, 'Could not cancel the run'))
    },
  })

  const renderActions = canCancel
    ? (run: RunOut) =>
        isTerminalRunStatus(run.status) ? null : (
          <Button
            variant="outline"
            size="sm"
            aria-label={`Cancel run ${run.id}`}
            disabled={cancel.isPending}
            onClick={() => cancel.mutate(run.id)}
          >
            Cancel
          </Button>
        )
    : undefined

  const summary = runs.data
    ? `Showing ${runs.data.items.length} of ${runs.data.total} runs, newest first.`
    : 'Pipeline runs, newest first.'

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="font-heading text-2xl font-semibold">Agent Runs</h1>
        <p className="text-sm text-muted-foreground">{summary}</p>
      </div>
      <Card>
        <CardContent>
          <RunsTable
            runs={runs.data?.items}
            isPending={runs.isPending}
            isError={runs.isError}
            showRunId
            renderActions={renderActions}
          />
        </CardContent>
      </Card>
    </section>
  )
}
