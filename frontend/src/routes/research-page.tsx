import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { researchRunQueryOptions, researchRunsQueryOptions } from '@/features/research/api'
import { ExternalLink, Field, PageHeading, Pagination, QueryState, StatusBadge } from '@/features/shared/ui'
import { formatDate } from '@/features/shared/helpers'
function ResearchDetail({ id }: { id: string }) {
  const query = useQuery({ ...researchRunQueryOptions(id), refetchInterval: 10000 })
  const data = query.data
  return (
    <QueryState query={query} label="research detail">
      {data && (
        <div className="space-y-5 rounded-lg border p-4">
          <div className="flex flex-wrap justify-between gap-3">
            <h2 className="font-semibold">
              {data.kind} research · {formatDate(data.startedAt)}
            </h2>
            <StatusBadge value={data.status} />
          </div>
          {data.articleId && (
            <Link className="text-sm underline" to={`/articles/${data.articleId}`}>
              Open article to regenerate research
            </Link>
          )}
          <p className="text-sm">Themes: {data.themesCovered.join(', ') || 'None recorded'}</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.phaseLatencyMs).map(([phase, ms]) => (
              <Badge key={phase} variant="outline">
                {phase}: {(ms / 1000).toFixed(1)}s
              </Badge>
            ))}
          </div>
          <details>
            <summary className="cursor-pointer font-medium">Queries ({data.queries.length})</summary>
            {data.queries.map((q, i) => (
              <div key={i} className="mt-2 rounded border p-3 text-sm">
                <StatusBadge value={q.status} /> {q.text}
                <p className="text-muted-foreground">
                  {q.sourceCount} sources · {q.searchActions} search actions
                </p>
                {q.error && <p className="text-destructive">{q.error}</p>}
              </div>
            ))}
          </details>
          <h3 className="font-medium">Findings ({data.findings.length})</h3>
          {data.findings.map((f) => (
            <div key={f.id} className="space-y-2 rounded border p-3 text-sm">
              <div className="flex gap-2">
                <Badge variant="outline">{f.claimType}</Badge>
                <Badge variant="secondary">{(f.confidence * 100).toFixed(0)}% confidence</Badge>
                {f.isPreprint && <Badge variant="outline">Preprint</Badge>}
              </div>
              <p className="font-medium">{f.claim}</p>
              <p className="text-muted-foreground">{f.evidence}</p>
              {f.downgradedFrom && <p className="text-amber-700">Downgraded from {f.downgradedFrom}</p>}
              {f.sources.map((s) => (
                <p key={s.id}>
                  <ExternalLink href={s.url}>{s.title}</ExternalLink> · Tier {s.tier} ·{' '}
                  {formatDate(s.publishedAt)}
                </p>
              ))}
            </div>
          ))}
          <h3 className="font-medium">Source ledger ({data.sources.length})</h3>
          {data.sources.map((s) => (
            <div key={s.id} className="rounded border p-3 text-sm">
              <ExternalLink href={s.url}>{s.title}</ExternalLink>
              <p className="text-muted-foreground">
                {s.publisher} · Tier {s.tier} · {s.accessMode} · {formatDate(s.publishedAt)} · {s.fetchStatus}
              </p>
            </div>
          ))}
        </div>
      )}
    </QueryState>
  )
}
export function ResearchPage() {
  const [params, setParams] = useSearchParams(),
    [offset, setOffset] = useState(0),
    [kind, setKind] = useState('')
  const runId = params.get('runId') ?? undefined,
    selected = params.get('researchRunId')
  const query = useQuery({
    ...researchRunsQueryOptions(20, offset, { runId, ...(kind ? { kind } : {}) }),
    refetchInterval: 10000,
  })
  return (
    <section className="space-y-5">
      <PageHeading title="Research" description="Research findings, query coverage, sources and latency." />
      <div className="flex items-end gap-3">
        <Field label="Research kind">
          <select
            className="h-9 rounded border bg-background px-2"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">All research</option>
            <option value="broad">Broad</option>
            <option value="deep">Deep</option>
            <option value="verification">Verification</option>
          </select>
        </Field>
        {runId && (
          <Button variant="outline" onClick={() => setParams({})}>
            Clear run filter
          </Button>
        )}
      </div>
      <QueryState query={query} label="research runs">
        {query.data?.items.length ? (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Kind</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Sources / findings</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>{run.kind}</TableCell>
                    <TableCell>
                      <StatusBadge value={run.status} />
                    </TableCell>
                    <TableCell>
                      {run.sourceCount} / {run.findingCount}
                    </TableCell>
                    <TableCell>{formatDate(run.startedAt)}</TableCell>
                    <TableCell>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setParams((p) => {
                            p.set('researchRunId', run.id)
                            return p
                          })
                        }
                      >
                        Open research
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <p className="rounded border p-8 text-sm text-muted-foreground">
            No research runs yet. Generate a blog from the Dashboard to start discovery.
          </p>
        )}
        <Pagination offset={offset} total={query.data?.total ?? 0} onChange={setOffset} />
      </QueryState>
      {selected && <ResearchDetail key={selected} id={selected} />}
    </section>
  )
}
