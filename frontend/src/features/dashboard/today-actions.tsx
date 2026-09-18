import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { createRun } from '@/features/runs/api'
import { selectTopic } from '@/features/topics/api'
import { articleQueryOptions } from '@/features/articles/api'
import { ArticleActions } from '@/features/articles/components/article-actions'
import { afterChange } from '@/features/shared/invalidation'
import { Field } from '@/features/shared/ui'
import { describeProblem, useCan } from '@/features/shared/helpers'
import type { TodayCardOut } from '@/lib/types'
export function GenerateOptions() {
  const [open, setOpen] = useState(false),
    [values, setValues] = useState({ topic: '', pillar: '', audience: '', tone: '', wordCount: '' }),
    client = useQueryClient()
  const mutation = useMutation({
    mutationFn: () =>
      createRun({
        ...(values.topic ? { topic: values.topic } : {}),
        ...(values.pillar ? { pillar: values.pillar } : {}),
        ...(values.audience ? { audience: values.audience } : {}),
        ...(values.tone ? { tone: values.tone } : {}),
        ...(values.wordCount ? { wordCount: Number(values.wordCount) } : {}),
      }),
    onSuccess: async () => {
      setOpen(false)
      toast.success('Run queued')
      await afterChange(client)
    },
    onError: (e) => toast.error(describeProblem(e)),
  })
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        Generate with options
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate with options</DialogTitle>
            <DialogDescription>Leave a field blank to use the saved defaults.</DialogDescription>
          </DialogHeader>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              mutation.mutate()
            }}
          >
            {(['topic', 'audience', 'tone'] as const).map((key) => (
              <Field key={key} label={key[0].toUpperCase() + key.slice(1)}>
                <Input
                  value={values[key]}
                  onChange={(e) => setValues({ ...values, [key]: e.target.value })}
                />
              </Field>
            ))}
            <Field label="Pillar">
              <select
                className="h-9 rounded border bg-background px-2"
                value={values.pillar}
                onChange={(e) => setValues({ ...values, pillar: e.target.value })}
              >
                <option value="">Scheduled pillar</option>
                {['A', 'B', 'C', 'D', 'E', 'NARRATIVE'].map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </Field>
            <Field label="Word count">
              <Input
                type="number"
                min={300}
                max={3000}
                value={values.wordCount}
                onChange={(e) => setValues({ ...values, wordCount: e.target.value })}
              />
            </Field>
            <DialogFooter>
              <Button disabled={mutation.isPending}>Generate</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
export function TodayActions({ today }: { today: TodayCardOut }) {
  const canGenerate = useCan('blog.generate'),
    client = useQueryClient()
  const article = useQuery({ ...articleQueryOptions(today.articleId ?? ''), enabled: !!today.articleId })
  const mutation = useMutation({
    mutationFn: () => selectTopic(today.recommendedTopic!.candidateId),
    onSuccess: () => afterChange(client),
    onError: (e) =>
      toast.error(describeProblem(e, 'Select this topic from Ideas to review any novelty warning')),
  })
  return (
    <div className="space-y-3">
      <p className="text-sm">
        {today.opportunitiesDiscovered} opportunities discovered ·{' '}
        {today.articleStatus ?? today.runStatus ?? 'No run yet'}
      </p>
      {today.headlineOptions && (
        <div className="space-y-1 text-sm">
          {Object.entries(today.headlineOptions).map(([key, value]) => (
            <p key={key}>
              <strong>{key}:</strong> {value}
            </p>
          ))}
        </div>
      )}
      {today.quality && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          {Object.entries(today.quality).map(([key, value]) => (
            <p key={key}>
              {key.replace(/([A-Z])/g, ' $1')}:{' '}
              {value === null
                ? 'pending'
                : typeof value === 'object'
                  ? Object.entries(value)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(', ')
                  : String(value)}
            </p>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {today.runId && (
          <Button variant="outline" asChild>
            <Link to={`/research?runId=${today.runId}`}>Review research</Link>
          </Button>
        )}
        {today.articleId && (
          <Button asChild>
            <Link to={`/articles/${today.articleId}`}>Open article</Link>
          </Button>
        )}
        {today.runId && (
          <Button variant="outline" asChild>
            <Link to={`/ideas?runId=${today.runId}`}>Change topic</Link>
          </Button>
        )}
        {canGenerate &&
          !today.articleId &&
          today.recommendedTopic &&
          ['WAITING_FOR_TOPIC', 'TOPICS_READY'].includes(today.runStatus ?? '') && (
            <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
              Select recommended topic
            </Button>
          )}
      </div>
      {article.data && <ArticleActions article={article.data} />}
    </div>
  )
}
