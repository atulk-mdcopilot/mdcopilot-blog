import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { createRun, isTerminalRunStatus, runDetailQueryOptions, type RunOut } from '@/features/runs/api'
import { afterChange } from '@/features/shared/invalidation'
import { describeProblem, formatDate, useCan } from '@/features/shared/helpers'
import { ExternalLink, Field, PageHeading, Pagination, QueryState, StatusBadge } from '@/features/shared/ui'
import {
  externalPostsQueryOptions,
  similarTopicsQuery,
  topicHistoryQueryOptions,
} from '@/features/topics/api'

type DraftRequest = {
  run: RunOut
  topic: string
}

function DraftRequestStatus({ request }: { request: DraftRequest }) {
  const canInspectRuns = useCan('blog.agent_runs')
  const detail = useQuery({
    ...runDetailQueryOptions(request.run.id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && isTerminalRunStatus(status) ? false : 3_000
    },
  })
  const run = detail.data ?? request.run
  const articleId = detail.data?.articleIds?.[0]

  return (
    <div role="status" className="space-y-3 rounded-lg border border-primary/30 bg-primary/5 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">Draft requested</h3>
          <p className="mt-1 text-sm">
            <span className="font-medium">{request.topic}</span> is queued for research and drafting.
          </p>
        </div>
        <StatusBadge value={run.status} />
      </div>
      <p className="font-mono text-xs text-muted-foreground">Run {run.id}</p>
      {detail.isError ? (
        <p className="text-sm text-muted-foreground">
          Live status is temporarily unavailable. The draft request is still recorded.
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {articleId ? (
          <Button asChild>
            <Link to={`/articles/${encodeURIComponent(articleId)}`}>Open draft</Link>
          </Button>
        ) : null}
        <Button asChild variant="outline">
          <Link to={`/ideas?runId=${encodeURIComponent(run.id)}`}>View topic</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/drafts">View all drafts</Link>
        </Button>
        {canInspectRuns ? (
          <Button asChild variant="outline">
            <Link to={`/runs?runId=${encodeURIComponent(run.id)}`}>View run details</Link>
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function TopicsPage() {
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [externalOffset, setExternalOffset] = useState(0)
  const [text, setText] = useState('')
  const [similarityText, setSimilarityText] = useState('')
  const [draftTopic, setDraftTopic] = useState('')
  const [draftRequest, setDraftRequest] = useState<DraftRequest | null>(null)
  const client = useQueryClient()
  const canGenerate = useCan('blog.generate')
  const history = useQuery(topicHistoryQueryOptions(q, 20, offset))
  const external = useQuery(externalPostsQueryOptions(20, externalOffset))
  const similar = useQuery({
    queryKey: ['topics', 'similar', similarityText],
    queryFn: () => similarTopicsQuery(similarityText),
    enabled: similarityText.length >= 3,
  })
  const createDraft = useMutation({
    mutationFn: (topic: string) => createRun({ topic }),
    onSuccess: async (run, topic) => {
      setDraftRequest({ run, topic })
      setDraftTopic('')
      toast.success('Draft generation queued')
      await afterChange(client)
    },
    onError: (error) => toast.error(describeProblem(error, 'Could not queue this draft')),
  })

  return (
    <section className="space-y-6">
      <PageHeading
        title="Generate"
        description="Start a draft from a specific topic, then browse selected topics and imported posts."
      >
        <Button asChild variant="outline">
          <Link to="/ideas">Browse discovered ideas</Link>
        </Button>
      </PageHeading>

      {canGenerate ? (
        <div className="space-y-4 rounded-lg border bg-card p-5">
          <div>
            <h2 className="font-semibold">Create a blog draft</h2>
            <p id="draft-topic-help" className="mt-1 text-sm text-muted-foreground">
              Enter the topic you want covered. The exact topic is queued immediately for research and
              drafting.
            </p>
          </div>
          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-end"
            onSubmit={(event) => {
              event.preventDefault()
              const topic = draftTopic.trim()
              if (topic) createDraft.mutate(topic)
            }}
          >
            <Field label="Topic for the new draft">
              <Input
                required
                maxLength={300}
                aria-describedby="draft-topic-help"
                placeholder="How ambient AI can reduce clinician documentation burden"
                value={draftTopic}
                disabled={createDraft.isPending}
                onChange={(event) => setDraftTopic(event.target.value)}
              />
            </Field>
            <Button disabled={createDraft.isPending || !draftTopic.trim()}>
              {createDraft.isPending ? 'Queuing draft…' : 'Create draft'}
            </Button>
          </form>
          {createDraft.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {describeProblem(createDraft.error, 'Could not queue this draft')}
            </p>
          ) : null}
        </div>
      ) : null}

      {draftRequest ? <DraftRequestStatus request={draftRequest} /> : null}

      <form
        className="flex items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          setQ(search)
          setOffset(0)
        }}
      >
        <Field label="Search topic history">
          <Input value={search} onChange={(event) => setSearch(event.target.value)} />
        </Field>
        <Button variant="outline">Search</Button>
      </form>
      <QueryState query={history} label="topic history">
        <div className="space-y-2">
          {!history.data?.items.length ? (
            <p className="text-sm text-muted-foreground">No selected topics match this search.</p>
          ) : null}
          {history.data?.items.map((topic) => (
            <div key={topic.id} className="rounded border p-3">
              <p className="font-medium">
                {topic.articleId ? (
                  <Link className="hover:underline" to={`/articles/${topic.articleId}`}>
                    {topic.title}
                  </Link>
                ) : (
                  topic.title
                )}
              </p>
              <p className="text-sm text-muted-foreground">
                Pillar {topic.pillar} · {topic.articleStatus ?? 'Topic selected'} ·{' '}
                {formatDate(topic.createdAt)}
              </p>
              <p className="mt-1 text-sm">{topic.thesis}</p>
            </div>
          ))}
        </div>
        <Pagination offset={offset} total={history.data?.total ?? 0} onChange={setOffset} />
      </QueryState>

      <div className="space-y-3 rounded-lg border p-4">
        <h2 className="font-semibold">Similarity search</h2>
        <form
          className="flex items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            setSimilarityText(text.trim())
          }}
        >
          <Field label="Topic or argument">
            <Input
              minLength={3}
              maxLength={1000}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </Field>
          <Button disabled={text.trim().length < 3}>Find similar topics</Button>
        </form>
        {similarityText ? (
          <QueryState query={similar} label="similar topics">
            {!similar.data?.items.length ? (
              <p className="text-sm text-muted-foreground">No similar topics found.</p>
            ) : null}
            {similar.data?.items.map((item) => (
              <p key={item.refId} className="text-sm">
                {item.title} · {item.kind} · {(item.similarity * 100).toFixed(0)}% similar
              </p>
            ))}
          </QueryState>
        ) : null}
      </div>

      <h2 className="font-semibold">External posts</h2>
      <QueryState query={external} label="external posts">
        {!external.data?.items.length ? (
          <p className="text-sm text-muted-foreground">No posts imported yet.</p>
        ) : null}
        {external.data?.items.map((post) => (
          <div key={post.id} className="rounded border p-3">
            <ExternalLink href={post.url}>{post.title}</ExternalLink>
            <p className="text-sm text-muted-foreground">
              {formatDate(post.publishedAt)} · Last synced {formatDate(post.lastSyncedAt)}
            </p>
            <p className="mt-1 text-sm">{post.excerpt}</p>
          </div>
        ))}
        <Pagination offset={externalOffset} total={external.data?.total ?? 0} onChange={setExternalOffset} />
      </QueryState>
    </section>
  )
}
