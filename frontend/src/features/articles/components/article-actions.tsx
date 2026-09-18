import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { sessionQueryOptions } from '@/features/auth/session'
import { regenerateArticle } from '@/features/articles/api'
import { approveArticle, rejectArticle, recheckArticle } from '@/features/quality/api'
import { afterChange } from '@/features/shared/invalidation'
import { Field } from '@/features/shared/ui'
import { describeProblem, useCan } from '@/features/shared/helpers'
import type { ArticleDetailOut } from '@/lib/types'

export function ArticleActions({ article, dirty = false }: { article: ArticleDetailOut; dirty?: boolean }) {
  const client = useQueryClient()
  const session = useQuery(sessionQueryOptions)
  const canGenerate = useCan('blog.generate'),
    canApprove = useCan('blog.approve'),
    canReview = useCan('blog.review')
  const [dialog, setDialog] = useState<'approve' | 'reject' | 'regenerate' | null>(null)
  const [mode, setMode] = useState<'draft' | 'publish'>('draft')
  const [reason, setReason] = useState(''),
    [instructions, setInstructions] = useState('')
  const [component, setComponent] = useState('article'),
    [sectionKey, setSectionKey] = useState('')
  const reviewable = ['READY_FOR_REVIEW', 'QUALITY_GATE_FAILED'].includes(article.status)
  const overrideNeeded = !article.gatesPassedOnCurrentVersion || article.status === 'QUALITY_GATE_FAILED'
  const canOverride =
    session.data?.user.role === 'admin' && article.gateOverridePolicy === 'admin_with_reason'
  const action = useMutation({
    mutationFn: (perform: () => Promise<unknown>) => perform(),
    onSuccess: async () => {
      setDialog(null)
      setReason('')
      toast.success('Article updated')
      await afterChange(client)
    },
    onError: (error) => toast.error(describeProblem(error, 'Could not update article')),
  })
  const disabled = action.isPending || dirty
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {canGenerate && reviewable && (
          <Button
            variant="outline"
            disabled={disabled}
            onClick={() => action.mutate(() => recheckArticle(article.id))}
          >
            Re-check
          </Button>
        )}
        {canApprove && reviewable && (
          <Button
            disabled={disabled || article.recheckRequired || (overrideNeeded && !canOverride)}
            onClick={() => setDialog('approve')}
          >
            Approve
          </Button>
        )}
        {canReview && ['READY_FOR_REVIEW', 'QUALITY_GATE_FAILED', 'APPROVED'].includes(article.status) && (
          <Button variant="outline" disabled={disabled} onClick={() => setDialog('reject')}>
            Reject
          </Button>
        )}
        {canGenerate && (reviewable || article.status === 'FAILED') && (
          <Button
            variant="outline"
            disabled={disabled}
            onClick={() => {
              setComponent(article.status === 'FAILED' ? 'research' : 'article')
              setDialog('regenerate')
            }}
          >
            Regenerate
          </Button>
        )}
      </div>
      {dirty && (
        <p className="text-sm text-amber-700">
          Save your edits before reviewing or regenerating this article.
        </p>
      )}
      {canApprove && reviewable && article.recheckRequired && (
        <p className="text-sm text-amber-700">Re-check this version before approval.</p>
      )}
      {canApprove && reviewable && overrideNeeded && !canOverride && (
        <p className="text-sm text-amber-700">
          Approval requires passing quality gates
          {article.gateOverridePolicy === 'admin_with_reason' ? ' or an administrator override' : ''}.
        </p>
      )}
      <Dialog open={dialog !== null} onOpenChange={(open) => !open && !action.isPending && setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {dialog === 'approve'
                ? 'Approve article'
                : dialog === 'reject'
                  ? 'Reject article'
                  : 'Regenerate'}
            </DialogTitle>
            <DialogDescription>
              {dialog === 'regenerate'
                ? 'The worker creates a new version and runs the required checks.'
                : 'This decision is recorded against the current article version.'}
            </DialogDescription>
          </DialogHeader>
          {dialog === 'approve' && (
            <div className="space-y-4">
              <fieldset className="space-y-2">
                <legend className="mb-2 text-sm font-medium">Approval mode</legend>
                <label className="flex gap-2">
                  <input type="radio" checked={mode === 'draft'} onChange={() => setMode('draft')} />
                  Approve as draft
                </label>
                <label className="flex gap-2">
                  <input type="radio" checked={mode === 'publish'} onChange={() => setMode('publish')} />
                  Approve for publishing
                </label>
              </fieldset>
              <p className="text-sm text-muted-foreground">
                Approval unlocks export, scheduling and publishing in the Publish tab.
              </p>
              {overrideNeeded && (
                <Field label="Override reason">
                  <Textarea maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />
                </Field>
              )}
            </div>
          )}
          {dialog === 'reject' && (
            <Field label="Reason">
              <Textarea maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
          )}
          {dialog === 'regenerate' && (
            <div className="space-y-3">
              <Field label="Component">
                <select
                  className="h-9 rounded-md border bg-background px-2"
                  value={component}
                  onChange={(e) => setComponent(e.target.value)}
                >
                  {(article.status === 'FAILED'
                    ? ['research']
                    : ['headline', 'introduction', 'section', 'pull_quote', 'cta', 'article', 'research']
                  ).map((item) => (
                    <option key={item} value={item}>
                      {item.replace('_', ' ')}
                    </option>
                  ))}
                </select>
              </Field>
              {component === 'section' && (
                <Field label="Section">
                  <select
                    className="h-9 rounded-md border bg-background px-2"
                    value={sectionKey}
                    onChange={(e) => setSectionKey(e.target.value)}
                  >
                    <option value="">Choose a section</option>
                    {article.sections
                      ?.filter((s) => s.key !== 'introduction')
                      .map((s) => (
                        <option key={s.key} value={s.key}>
                          {s.heading ?? s.key}
                        </option>
                      ))}
                  </select>
                </Field>
              )}
              <Field label="Instructions">
                <Textarea
                  maxLength={2000}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                />
              </Field>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" disabled={action.isPending} onClick={() => setDialog(null)}>
              Cancel
            </Button>
            {dialog === 'approve' && (
              <Button
                disabled={action.isPending || !article.currentVersionId || (overrideNeeded && !reason.trim())}
                onClick={() =>
                  action.mutate(() =>
                    approveArticle(article.id, {
                      mode,
                      versionId: article.currentVersionId!,
                      ...(overrideNeeded ? { overrideReason: reason } : {}),
                    }),
                  )
                }
              >
                {overrideNeeded ? 'Override and approve' : 'Approve'}
              </Button>
            )}
            {dialog === 'reject' && (
              <Button
                variant="destructive"
                disabled={action.isPending || !reason.trim()}
                onClick={() => action.mutate(() => rejectArticle(article.id, reason))}
              >
                Reject article
              </Button>
            )}
            {dialog === 'regenerate' && (
              <Button
                disabled={action.isPending || (component === 'section' && !sectionKey)}
                onClick={() =>
                  action.mutate(() =>
                    regenerateArticle(article.id, {
                      component,
                      ...(component === 'section' ? { sectionKey } : {}),
                      ...(instructions.trim() ? { instructions } : {}),
                    }),
                  )
                }
              >
                Start regeneration
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// A timezone-aware ISO timestamp is sent; the form explicitly uses the browser's local zone.
export function ScheduleFields({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Field label={`Schedule date and time (${Intl.DateTimeFormat().resolvedOptions().timeZone})`}>
      <Input type="datetime-local" value={value} onChange={(e) => onChange(e.target.value)} required />
    </Field>
  )
}
