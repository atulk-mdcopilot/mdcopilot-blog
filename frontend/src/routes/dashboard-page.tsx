import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { dashboardQueryOptions } from '@/features/dashboard/api'
import { GenerateOptions, TodayActions } from '@/features/dashboard/today-actions'
import { createRun, runsQueryOptions } from '@/features/runs/api'
import { RunsTable } from '@/features/runs/runs-table'
import { describeProblem, useCan } from '@/features/shared/helpers'
import { afterChange } from '@/features/shared/invalidation'
import { PageHeading, QueryState, StatusBadge } from '@/features/shared/ui'

export function DashboardPage() {
  const client = useQueryClient()
  const canGenerate = useCan('blog.generate')
  const canInspectRuns = useCan('blog.agent_runs')
  const dashboard = useQuery(dashboardQueryOptions())
  const recentRuns = useQuery(runsQueryOptions(5, 0))
  const generate = useMutation({
    mutationFn: () => createRun(),
    onSuccess: async () => {
      toast.success('Run queued')
      await afterChange(client)
    },
    onError: (error) => toast.error(describeProblem(error)),
  })
  const data = dashboard.data

  return (
    <section className="space-y-6">
      <PageHeading title="Dashboard" description="Generate, review and publish your next blog.">
        {canGenerate && (
          <div className="flex flex-wrap gap-2">
            <GenerateOptions />
            <Button disabled={generate.isPending} onClick={() => generate.mutate()}>
              {generate.isPending ? 'Queuing…' : 'Generate blog'}
            </Button>
          </div>
        )}
      </PageHeading>
      <QueryState query={dashboard} label="dashboard">
        {data && (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                ['Generated', data.metrics.postsGenerated, `Last ${data.metrics.windowDays} days`],
                ['Pending articles', data.metrics.postsPending, 'Awaiting review or publication'],
                ['Published', data.metrics.postsPublished, `Last ${data.metrics.windowDays} days`],
              ].map(([label, value, caption]) => (
                <Card key={label}>
                  <CardHeader>
                    <CardTitle>{label}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-3xl font-semibold">{value}</p>
                    <p className="text-xs text-muted-foreground">{caption}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Today · {data.today.date}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {data.today.recommendedTopic && (
                  <div>
                    <h2 className="font-semibold">{data.today.recommendedTopic.title}</h2>
                    <p className="text-sm text-muted-foreground">{data.today.recommendedTopic.whyNow}</p>
                  </div>
                )}
                <TodayActions today={data.today} />
                <div className="flex flex-wrap gap-3">
                  {data.pipeline.stages.map((stage) => (
                    <div key={stage.key} className="space-y-1 text-xs">
                      <p>{stage.label}</p>
                      <StatusBadge value={stage.status} />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </QueryState>
      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Recent runs</CardTitle>
          {canInspectRuns && (
            <Button asChild variant="outline" size="sm">
              <Link to="/runs">View all runs</Link>
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <RunsTable
            runs={recentRuns.data?.items}
            isPending={recentRuns.isPending}
            isError={recentRuns.isError}
            renderActions={
              canInspectRuns
                ? (run) => (
                    <Button asChild variant="outline" size="sm">
                      <Link to={`/runs?runId=${run.id}`}>Details</Link>
                    </Button>
                  )
                : undefined
            }
          />
        </CardContent>
      </Card>
    </section>
  )
}
