import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  topicRoundQueryOptions,
  generateTopics,
  rejectTopic,
  selectTopic,
  updateTopic,
} from '@/features/topics/api'
import { afterChange } from '@/features/shared/invalidation'
import { ExternalLink, Field, PageHeading, QueryState, StatusBadge } from '@/features/shared/ui'
import { describeProblem, useCan } from '@/features/shared/helpers'
import { ApiError } from '@/lib/api'
import type { TopicCandidateOut } from '@/lib/types'
export function IdeasPage() {
  const client = useQueryClient(),
    [params] = useSearchParams(),
    navigate = useNavigate()
  const canGenerate = useCan('blog.generate'),
    canEdit = useCan('blog.edit')
  const [roundNo, setRoundNo] = useState('')
  const round = useQuery({
    ...topicRoundQueryOptions(params.get('runId') ?? undefined, roundNo ? Number(roundNo) : undefined),
    refetchInterval: 5000,
  })
  const [dialog, setDialog] = useState<{
      kind: 'warn' | 'edit' | 'reject'
      candidate: TopicCandidateOut
    } | null>(null),
    [reason, setReason] = useState('')
  const [patch, setPatch] = useState<Record<string, string>>({})
  const action = useMutation({
    mutationFn: (perform: () => Promise<unknown>) => perform(),
    onSuccess: async () => {
      setDialog(null)
      toast.success('Topic updated')
      await afterChange(client)
    },
    onError: (e) => toast.error(describeProblem(e, 'Could not update topic')),
  })
  function choose(candidate: TopicCandidateOut, confirm = false) {
    action.mutate(async () => {
      const result = await selectTopic(candidate.id, confirm)
      if (result.articleId) void navigate(`/articles/${result.articleId}`)
    })
  }
  const editableRound =
    round.data && !['QUEUED', 'RESEARCHING', 'PRODUCING', 'CANCELLED'].includes(round.data.runStatus)
  return (
    <section className="space-y-5">
      <PageHeading
        title="Today's Ideas"
        description="Compare the evidence, editorial angle and novelty before choosing a topic."
      >
        {canGenerate && editableRound && (
          <Button
            variant="outline"
            disabled={action.isPending}
            onClick={() => action.mutate(() => generateTopics(round.data!.runId))}
          >
            Regenerate topics
          </Button>
        )}
      </PageHeading>
      {round.error instanceof ApiError && round.error.status === 404 ? (
        <p className="rounded border p-8 text-sm text-muted-foreground">
          No ideas yet.{' '}
          <Link className="underline" to="/">
            Generate a blog from the Dashboard.
          </Link>
        </p>
      ) : (
        <QueryState query={round} label="ideas">
          {round.data && (
            <>
              <div className="flex items-center gap-3">
                <Field label="Round">
                  <select
                    value={roundNo || round.data.round}
                    className="h-9 rounded border bg-background px-2"
                    onChange={(e) => setRoundNo(e.target.value)}
                  >
                    {round.data.roundsAvailable.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </Field>
                <StatusBadge value={round.data.runStatus} />
              </div>
              {round.data.shortfall && (
                <p role="status" className="rounded border border-amber-300 p-3 text-sm">
                  Fewer than three viable topics remain. You can still choose an available topic below.
                </p>
              )}
              <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
                {round.data.items.map((c) => (
                  <article key={c.id} className="flex flex-col gap-4 rounded-lg border bg-card p-5">
                    <div className="flex justify-between gap-2">
                      <Badge variant="outline">Pillar {c.pillar}</Badge>
                      <StatusBadge value={c.status} />
                    </div>
                    <h2 className="font-semibold">{c.title}</h2>
                    <p className="text-sm">{c.hook}</p>
                    <p className="text-sm">
                      <strong>Why now:</strong> {c.whyNow}
                    </p>
                    <p className="text-sm">
                      <strong>Thesis:</strong> {c.thesis}
                    </p>
                    <p className="text-sm">
                      <strong>MDCopilot angle:</strong> {c.mdcopilotConnection}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      For {c.targetAudience} · Total score {c.totalScore?.toFixed(2) ?? '—'}
                    </p>
                    <details className="text-sm">
                      <summary className="cursor-pointer font-medium">Scores and evidence</summary>
                      <div className="mt-3 space-y-3">
                        {Object.entries(c.scoreBreakdown).map(([key, score]) => (
                          <div key={key}>
                            <p>
                              {key}: {score.score.toFixed(2)} × {score.weight}
                            </p>
                            <p className="text-xs text-muted-foreground">{score.justification}</p>
                          </div>
                        ))}
                        {c.novelty?.neighbours.map((n) => (
                          <p key={n.refId}>
                            Similar: {n.title} ({(n.similarity * 100).toFixed(0)}%)
                          </p>
                        ))}
                        {c.sources.map((s) => (
                          <p key={s.id}>
                            <ExternalLink href={s.url}>{s.title}</ExternalLink> · Tier {s.tier}
                          </p>
                        ))}
                        {c.relevantNews.map((n, i) => (
                          <p key={i}>
                            <ExternalLink href={n.url}>{n.title}</ExternalLink>
                          </p>
                        ))}
                      </div>
                    </details>
                    <div className="mt-auto flex flex-wrap gap-2">
                      {canGenerate &&
                        editableRound &&
                        !['REJECTED', 'DISMISSED', 'SUPERSEDED', 'SELECTED'].includes(c.status) && (
                          <Button
                            disabled={action.isPending}
                            aria-label={`Select topic: ${c.title}`}
                            onClick={() =>
                              c.status === 'WARNED' || c.novelty?.decision === 'WARN'
                                ? setDialog({ kind: 'warn', candidate: c })
                                : choose(c)
                            }
                          >
                            Select
                          </Button>
                        )}
                      {canEdit && !['SELECTED', 'SUPERSEDED'].includes(c.status) && (
                        <Button
                          variant="outline"
                          aria-label={`Edit topic: ${c.title}`}
                          onClick={() => {
                            setPatch(
                              Object.fromEntries(
                                [
                                  'title',
                                  'hook',
                                  'whyNow',
                                  'thesis',
                                  'angle',
                                  'coreArgument',
                                  'targetAudience',
                                  'pillar',
                                ].map((key) => [key, String(c[key as keyof TopicCandidateOut])]),
                              ),
                            )
                            setDialog({ kind: 'edit', candidate: c })
                          }}
                        >
                          Edit
                        </Button>
                      )}
                      {canEdit && c.status !== 'SELECTED' && c.status !== 'DISMISSED' && (
                        <Button
                          variant="ghost"
                          aria-label={`Reject topic: ${c.title}`}
                          onClick={() => {
                            setReason('')
                            setDialog({ kind: 'reject', candidate: c })
                          }}
                        >
                          Reject
                        </Button>
                      )}
                      {c.articleId && (
                        <Link className="self-center text-sm underline" to={`/articles/${c.articleId}`}>
                          Open article
                        </Link>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
        </QueryState>
      )}
      <Dialog open={!!dialog} onOpenChange={(open) => !open && !action.isPending && setDialog(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {dialog?.kind === 'warn'
                ? 'This topic overlaps earlier coverage'
                : dialog?.kind === 'edit'
                  ? 'Edit topic'
                  : 'Reject topic'}
            </DialogTitle>
            <DialogDescription>
              {dialog?.kind === 'warn'
                ? 'Review the novelty neighbours before selecting this topic.'
                : dialog?.kind === 'edit'
                  ? 'Text changes are saved; novelty and scores are rechecked during production.'
                  : 'Record why this topic should be dismissed.'}
            </DialogDescription>
          </DialogHeader>
          {dialog?.kind === 'warn' &&
            dialog.candidate.novelty?.neighbours.map((n) => (
              <p key={n.refId} className="text-sm">
                {n.title} · {(n.similarity * 100).toFixed(0)}% similar
              </p>
            ))}
          {dialog?.kind === 'edit' &&
            Object.entries(patch).map(([key, value]) => (
              <Field key={key} label={key.replace(/([A-Z])/g, ' $1')}>
                <Textarea value={value} onChange={(e) => setPatch({ ...patch, [key]: e.target.value })} />
              </Field>
            ))}
          {dialog?.kind === 'reject' && (
            <Field label="Reason">
              <Textarea value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)} disabled={action.isPending}>
              Cancel
            </Button>
            <Button
              disabled={
                action.isPending ||
                (dialog?.kind === 'reject' && !reason.trim()) ||
                (dialog?.kind === 'edit' && !patch.title?.trim())
              }
              onClick={() => {
                if (!dialog) return
                if (dialog.kind === 'warn') choose(dialog.candidate, true)
                else
                  action.mutate(() =>
                    dialog.kind === 'edit'
                      ? updateTopic(dialog.candidate.id, patch)
                      : rejectTopic(dialog.candidate.id, reason),
                  )
              }}
            >
              {dialog?.kind === 'warn'
                ? 'Select anyway'
                : dialog?.kind === 'edit'
                  ? 'Save topic'
                  : 'Reject topic'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
