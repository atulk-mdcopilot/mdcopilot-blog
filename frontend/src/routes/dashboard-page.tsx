import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { hasPermission } from '@/features/auth/permissions'
import { sessionQueryOptions } from '@/features/auth/session'
import { RUNS_QUERY_KEY, createRun, runsQueryOptions } from '@/features/runs/api'
import { RunsTable } from '@/features/runs/runs-table'
import { problemMessage } from '@/lib/api'

const RECENT_RUNS_LIMIT = 10

export function DashboardPage() {
  const queryClient = useQueryClient()
  const { data: session } = useQuery(sessionQueryOptions)
  const runs = useQuery(runsQueryOptions(RECENT_RUNS_LIMIT))
  const canGenerate = hasPermission(session?.user, 'blog.generate')

  const generate = useMutation({
    mutationFn: createRun,
    onSuccess: async (run) => {
      toast.success('Run queued', { description: `Run for ${run.runDate} is ${run.status}.` })
      await queryClient.invalidateQueries({ queryKey: RUNS_QUERY_KEY })
    },
    onError: (error) => {
      toast.error(problemMessage(error, 'Could not start the run'))
    },
  })

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Start a pipeline run and follow its progress.</p>
        </div>
        {canGenerate ? (
          <Button onClick={() => generate.mutate()} disabled={generate.isPending}>
            {generate.isPending ? 'Starting...' : "Generate today's blog"}
          </Button>
        ) : null}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Recent runs</h2>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <RunsTable runs={runs.data?.items} isPending={runs.isPending} isError={runs.isError} />
        </CardContent>
      </Card>
    </section>
  )
}
