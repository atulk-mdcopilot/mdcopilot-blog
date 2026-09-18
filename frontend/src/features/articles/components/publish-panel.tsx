import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import DOMPurify from 'dompurify'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  exportArticle,
  publishArticle,
  publicationsQueryOptions,
  confirmPublished,
  scheduleArticle,
  unscheduleArticle,
} from '@/features/publishing/api'
import { ScheduleFields } from './article-actions'
import { afterChange } from '@/features/shared/invalidation'
import { ExternalLink, Field, QueryState, StatusBadge } from '@/features/shared/ui'
import { describeProblem, formatDate, useCan } from '@/features/shared/helpers'
import type { ArticleDetailOut, ExportBundleOut } from '@/lib/types'

function download(name: string, content: string, mime: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}
export function PublishPanel({ article }: { article: ArticleDetailOut }) {
  const client = useQueryClient(),
    canPublish = useCan('blog.publish'),
    canSchedule = useCan('blog.schedule')
  const publications = useQuery(publicationsQueryOptions(article.id))
  const [bundle, setBundle] = useState<ExportBundleOut | null>(null),
    [url, setUrl] = useState(''),
    [date, setDate] = useState('')
  const [publishConfirm, setPublishConfirm] = useState(false)
  const action = useMutation({
    mutationFn: (perform: () => Promise<unknown>) => perform(),
    onSuccess: async () => {
      toast.success('Publication updated')
      setPublishConfirm(false)
      await afterChange(client)
    },
    onError: (e) => toast.error(describeProblem(e, 'Publishing action failed')),
  })
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Copied')
    } catch {
      toast.error('Clipboard unavailable. Use the download instead.')
    }
  }
  async function copyArticle() {
    if (!bundle) return
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([DOMPurify.sanitize(bundle.html)], { type: 'text/html' }),
          'text/plain': new Blob([bundle.text], { type: 'text/plain' }),
        }),
      ])
      toast.success('Article copied with formatting')
    } catch {
      toast.error('Clipboard unavailable. Download the HTML to continue.')
    }
  }
  return (
    <div className="space-y-5">
      <div className="rounded-md border bg-muted/40 p-3 text-sm">
        Approved version:{' '}
        {article.approvedVersionId
          ? `v${article.approvedVersionId === article.currentVersionId ? article.versionNo : ' (previous)'}`
          : 'none'}{' '}
        · Mode: {article.approvalMode ?? 'not approved'}
        {article.scheduledFor && <p>Scheduled for {formatDate(article.scheduledFor)}</p>}
        {article.publishedUrl && (
          <p>
            <ExternalLink href={article.publishedUrl}>View published article</ExternalLink>
          </p>
        )}
      </div>
      {canPublish && ['APPROVED', 'SCHEDULED', 'EXPORTED'].includes(article.status) && (
        <div>
          <Button
            disabled={action.isPending}
            onClick={() =>
              action.mutate(async () => {
                const data = await exportArticle(article.id)
                setBundle(data)
              })
            }
          >
            Export
          </Button>
          <p className="mt-2 text-sm text-muted-foreground">
            Create the approved article's HTML and metadata bundle, then confirm its live URL after
            publishing.
          </p>
        </div>
      )}
      {bundle && (
        <div className="space-y-3 rounded-md border p-4">
          <p className="font-medium">Export ready: {bundle.title}</p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void copyArticle()}>Copy article</Button>
            {(['title', 'slug', 'excerpt'] as const).map((key) => (
              <Button key={key} variant="outline" onClick={() => void copy(bundle[key])}>
                Copy {key}
              </Button>
            ))}
            <Button
              variant="outline"
              onClick={() =>
                download(`${bundle.slug}-bundle.json`, JSON.stringify(bundle, null, 2), 'application/json')
              }
            >
              Download bundle
            </Button>
            <Button
              variant="outline"
              onClick={() => download(`${bundle.slug}.html`, bundle.html, 'text/html')}
            >
              Download HTML
            </Button>
          </div>
        </div>
      )}
      {canPublish && article.status === 'EXPORTED' && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            action.mutate(() => confirmPublished(article.id, url))
          }}
        >
          <Field label="Published URL">
            <Input
              type="url"
              pattern="https?://.*"
              maxLength={2000}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
          </Field>
          <Button disabled={action.isPending || !url.trim()}>Confirm published</Button>
        </form>
      )}
      {canPublish &&
        article.networkPublishingActive &&
        ['APPROVED', 'PUBLISH_FAILED'].includes(article.status) && (
          <div className="space-y-3">
            {publishConfirm ? (
              <div className="rounded border p-3">
                <p className="mb-3 text-sm">
                  Send the approved article to MDCopilot as{' '}
                  {article.approvalMode === 'draft' ? 'a draft' : 'a published post'}?
                </p>
                <div className="flex gap-2">
                  <Button
                    disabled={action.isPending}
                    onClick={() => action.mutate(() => publishArticle(article.id))}
                  >
                    Confirm publish
                  </Button>
                  <Button variant="outline" onClick={() => setPublishConfirm(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button disabled={action.isPending} onClick={() => setPublishConfirm(true)}>
                Publish to MDCopilot
              </Button>
            )}
          </div>
        )}
      {canSchedule && (!article.networkPublishingActive || canPublish) && article.status === 'APPROVED' && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            const at = new Date(date)
            if (!Number.isFinite(at.getTime()) || at.getTime() <= Date.now()) {
              toast.error('Choose a future date and time')
              return
            }
            action.mutate(() => scheduleArticle(article.id, at.toISOString()))
          }}
        >
          <ScheduleFields value={date} onChange={setDate} />
          <Button disabled={action.isPending || !date}>Schedule article</Button>
          <p className="text-sm text-muted-foreground">
            {article.networkPublishingActive
              ? 'Publishes automatically at this time after approval.'
              : 'Prepares the export at this time.'}
          </p>
        </form>
      )}
      {canSchedule && article.status === 'SCHEDULED' && (
        <Button
          variant="outline"
          disabled={action.isPending}
          onClick={() => action.mutate(() => unscheduleArticle(article.id))}
        >
          Unschedule
        </Button>
      )}
      <div>
        <h3 className="mb-2 font-medium">Publication history</h3>
        <QueryState query={publications} label="publications">
          {!publications.data?.length && (
            <p className="text-sm text-muted-foreground">No publication attempts yet.</p>
          )}
          {publications.data?.map((p) => (
            <div key={p.id} className="mb-2 rounded border p-3 text-sm">
              <StatusBadge value={p.status} />{' '}
              <span>
                {p.publisher} · {p.asDraft ? 'Draft' : 'Published post'} · {p.attempts} attempts
              </span>
              <p>{formatDate(p.updatedAt)}</p>
              {p.publishedUrl && <ExternalLink href={p.publishedUrl}>Open publication</ExternalLink>}
              {p.lastError && (
                <p className="text-destructive">
                  {String(p.lastError.message ?? p.lastError.detail ?? 'Publication failed')}
                </p>
              )}
            </div>
          ))}
        </QueryState>
      </div>
    </div>
  )
}
