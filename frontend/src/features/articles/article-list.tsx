import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { articlesQueryOptions } from '@/features/articles/api'
import { pillarsQueryOptions } from '@/features/settings/api'
import { ExternalLink, Field, PageHeading, Pagination, QueryState, StatusBadge } from '@/features/shared/ui'
import { formatDate } from '@/features/shared/helpers'
export function ArticleList({
  view,
  title,
  description,
}: {
  view: 'drafts' | 'review' | 'published'
  title: string
  description: string
}) {
  const [offset, setOffset] = useState(0),
    [pillar, setPillar] = useState(''),
    [search, setSearch] = useState(''),
    [q, setQ] = useState('')
  const articles = useQuery(
      articlesQueryOptions(view, 20, offset, { ...(pillar ? { pillar } : {}), ...(q ? { q } : {}) }),
    ),
    pillars = useQuery(pillarsQueryOptions())
  return (
    <section className="space-y-5">
      <PageHeading title={title} description={description} />
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          setQ(search)
          setOffset(0)
        }}
      >
        <Field label="Search">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Title or slug" />
        </Field>
        <Field label="Pillar">
          <select
            className="h-9 rounded border bg-background px-2"
            value={pillar}
            onChange={(e) => {
              setPillar(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">All pillars</option>
            {pillars.data?.map((p) => (
              <option key={p.key} value={p.key}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
        <Button variant="outline">Search</Button>
      </form>
      <QueryState query={articles} label="articles">
        {!articles.data?.items.length ? (
          <p className="rounded-lg border p-8 text-sm text-muted-foreground">
            No articles match these filters.
          </p>
        ) : (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Article</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Quality</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>{view === 'published' ? 'Publication' : 'Updated'}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {articles.data.items.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="max-w-96 whitespace-normal">
                      <Link className="font-medium hover:underline" to={`/articles/${a.id}`}>
                        {a.title ?? 'Untitled draft'}
                      </Link>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Pillar {a.pillar} · {a.category} · {a.wordCount ?? '—'} words
                      </p>
                    </TableCell>
                    <TableCell>
                      <StatusBadge value={a.status} />
                      <p className="mt-1 text-xs text-muted-foreground">Pipeline: {a.pipelineStatus}</p>
                    </TableCell>
                    <TableCell>
                      <Badge variant={a.gateBadge.passed === false ? 'destructive' : 'secondary'}>
                        {a.gateBadge.recheckRequired
                          ? 'Recheck required'
                          : a.gateBadge.passed === null
                            ? 'Pending checks'
                            : a.gateBadge.passed
                              ? 'Gates passed'
                              : 'Gates failed'}
                      </Badge>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Fact check: {a.factCheckVerdict ?? 'pending'}
                        {a.editorialScore !== null
                          ? ` · Editorial ${(a.editorialScore * 100).toFixed(0)}%`
                          : ''}
                      </p>
                      {a.gateBadge.failedGates.length > 0 && (
                        <p className="mt-1 text-xs text-destructive">{a.gateBadge.failedGates.join(', ')}</p>
                      )}
                    </TableCell>
                    <TableCell>{a.currentVersionNo ?? '—'}</TableCell>
                    <TableCell className="text-xs">
                      {view === 'published' ? (
                        <>
                          <p>
                            {a.scheduledFor
                              ? `Scheduled ${formatDate(a.scheduledFor)}`
                              : a.publishedAt
                                ? formatDate(a.publishedAt)
                                : 'Awaiting publication'}
                          </p>
                          {a.publishedUrl && (
                            <ExternalLink href={a.publishedUrl}>View live post</ExternalLink>
                          )}
                        </>
                      ) : (
                        formatDate(a.updatedAt)
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
        <Pagination offset={offset} total={articles.data?.total ?? 0} onChange={setOffset} />
      </QueryState>
    </section>
  )
}
