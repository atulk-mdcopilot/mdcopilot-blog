import { lazy, Suspense, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useBlocker, useParams } from 'react-router'
import DOMPurify from 'dompurify'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { articleQueryOptions, editArticle, selectTitle } from '@/features/articles/api'
import { previewQueryOptions } from '@/features/publishing/api'
import { ArticleActions } from '@/features/articles/components/article-actions'
import { PublishPanel } from '@/features/articles/components/publish-panel'
import { EvidencePanel } from '@/features/articles/components/evidence-panel'
import { VersionPanel } from '@/features/articles/components/version-panel'
import { afterChange } from '@/features/shared/invalidation'
import { Field, PageHeading, QueryState, StatusBadge } from '@/features/shared/ui'
import { describeProblem, useCan } from '@/features/shared/helpers'
import type { ArticleDetailOut, ArticleEdit, TitleOptions } from '@/lib/types'
const MarkdownEditor = lazy(() =>
  import('@/features/articles/components/markdown-editor').then((m) => ({ default: m.MarkdownEditor })),
)

function Editor({ article }: { article: ArticleDetailOut }) {
  const client = useQueryClient(),
    canEdit = useCan('blog.edit')
  const [baseVersionId, setBaseVersionId] = useState(article.currentVersionId)
  const [form, setForm] = useState(() => ({
    contentMarkdown: article.contentMarkdown ?? '',
    pullQuote: article.pullQuote ?? '',
    cta: article.cta ?? '',
    excerpt: article.excerpt ?? '',
    titleOptions: article.titleOptions ?? { provocative: '', operational: '', visionary: '' },
    seo: article.seo,
    tags: article.tags,
    category: article.category,
  }))
  const [dirty, setDirty] = useState(false),
    [customTitle, setCustomTitle] = useState(''),
    [activeTab, setActiveTab] = useState('edit')
  const editable = canEdit && ['READY_FOR_REVIEW', 'QUALITY_GATE_FAILED', 'APPROVED'].includes(article.status)
  const preview = useQuery({ ...previewQueryOptions(article.id), enabled: !!article.currentVersionId })
  const blocker = useBlocker(({ nextLocation }) => dirty && nextLocation.pathname !== '/login')
  useEffect(() => {
    if (!dirty) return
    const listener = (e: BeforeUnloadEvent) => {
      e.preventDefault()
    }
    window.addEventListener('beforeunload', listener)
    return () => window.removeEventListener('beforeunload', listener)
  }, [dirty])
  function update(patch: Partial<typeof form>) {
    setForm((value) => ({ ...value, ...patch }))
    setDirty(true)
  }
  function reset(data: ArticleDetailOut) {
    setBaseVersionId(data.currentVersionId)
    setForm({
      contentMarkdown: data.contentMarkdown ?? '',
      pullQuote: data.pullQuote ?? '',
      cta: data.cta ?? '',
      excerpt: data.excerpt ?? '',
      titleOptions: data.titleOptions ?? { provocative: '', operational: '', visionary: '' },
      seo: data.seo,
      tags: data.tags,
      category: data.category,
    })
    setDirty(false)
  }
  const save = useMutation({
    mutationFn: () => {
      const { seo, ...fields } = form
      const body: ArticleEdit = { baseVersionId: baseVersionId!, ...fields }
      if (seo) {
        const { internalLinkSuggestions: _links, externalReferences: _refs, ...editableSeo } = seo
        void _links
        void _refs
        body.seo = editableSeo
      }
      return editArticle(article.id, body)
    },
    onSuccess: async (data) => {
      reset(data)
      client.setQueryData(articleQueryOptions(article.id).queryKey, data)
      toast.success('Saved as a new version. Re-check before approval.')
      await afterChange(client)
    },
    onError: (error) => toast.error(describeProblem(error, 'Could not save article')),
  })
  const title = useMutation({
    mutationFn: (body: { key: string } | { customTitle: string }) => selectTitle(article.id, body),
    onSuccess: async () => {
      toast.success('Headline selected')
      await afterChange(client)
    },
    onError: (e) => toast.error(describeProblem(e)),
  })
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">
            {article.selectedTitle ?? article.titleOptions?.operational ?? 'Untitled draft'}
          </h2>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge value={article.status} />
            <span className="text-sm text-muted-foreground">
              Version {article.versionNo ?? '—'} · Pillar {article.pillar} · {article.pipelineStatus}
            </span>
          </div>
        </div>
        <Link className="text-sm underline" to={`/runs?runId=${encodeURIComponent(article.runId)}`}>
          View run
        </Link>
      </div>
      <ArticleActions article={article} dirty={dirty} />
      {baseVersionId !== article.currentVersionId && (
        <div role="alert" className="rounded border border-amber-300 p-3 text-sm">
          A newer version is available. Your local edits are preserved.{' '}
          <Button
            variant="outline"
            onClick={() => {
              if (!dirty || window.confirm('Discard unsaved edits and load the latest version?'))
                reset(article)
            }}
          >
            Load latest version
          </Button>
        </div>
      )}
      {blocker.state === 'blocked' && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded border p-3">
          <p>You have unsaved edits.</p>
          <Button onClick={() => blocker.reset()}>Keep editing</Button>
          <Button variant="destructive" onClick={() => blocker.proceed()}>
            Discard and leave
          </Button>
        </div>
      )}
      <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.9fr)_minmax(440px,1.2fr)]">
        <aside className="min-w-0 rounded-lg border bg-card p-4">
          <EvidencePanel article={article} />
        </aside>
        <div className="min-w-0 rounded-lg border bg-card p-4">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList aria-label="Editor" className="flex h-auto flex-wrap justify-start">
              {['edit', 'preview', 'headline', 'seo', 'versions', 'publish'].map((tab) => (
                <TabsTrigger key={tab} value={tab}>
                  {tab === 'seo' ? 'SEO' : tab[0].toUpperCase() + tab.slice(1)}
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="edit" className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Keep the introduction followed by the six section headings. Cite existing sources with [S1],
                [S2], etc.
              </p>
              <Suspense fallback={<Skeleton className="h-96" aria-label="Loading editor" />}>
                <MarkdownEditor
                  value={form.contentMarkdown}
                  onChange={(contentMarkdown) => update({ contentMarkdown })}
                  readOnly={!editable}
                />
              </Suspense>
              {(['pullQuote', 'cta', 'excerpt'] as const).map((key) => (
                <Field
                  key={key}
                  label={key === 'pullQuote' ? 'Pull quote' : key === 'cta' ? 'CTA' : 'Excerpt'}
                >
                  <Textarea
                    readOnly={!editable}
                    maxLength={key === 'excerpt' ? 500 : undefined}
                    value={form[key]}
                    onChange={(e) => update({ [key]: e.target.value })}
                  />
                </Field>
              ))}
            </TabsContent>
            <TabsContent value="preview">
              <p className="mb-3 text-sm text-muted-foreground">
                Preview of the saved version{dirty ? '; save to preview your edits' : ''}.
              </p>
              {article.currentVersionId ? (
                <QueryState query={preview} label="preview">
                  {preview.data?.issues.map((issue, i) => (
                    <p className="mb-2 text-sm text-amber-700" key={i}>
                      {issue.field}: {issue.message}
                    </p>
                  ))}
                  <article
                    className="article-preview"
                    dangerouslySetInnerHTML={{
                      __html: DOMPurify.sanitize(preview.data?.html ?? '', {
                        ALLOWED_TAGS: [
                          'h2',
                          'h3',
                          'p',
                          'strong',
                          'em',
                          's',
                          'a',
                          'ul',
                          'ol',
                          'li',
                          'blockquote',
                          'img',
                        ],
                        ALLOWED_ATTR: ['href', 'rel', 'src', 'alt'],
                        ALLOWED_URI_REGEXP: /^https?:\/\//i,
                        ADD_URI_SAFE_ATTR: ['rel'],
                      }),
                    }}
                  />
                </QueryState>
              ) : (
                <p>The writer has not produced a version yet.</p>
              )}
            </TabsContent>
            <TabsContent value="headline" className="space-y-4">
              {(Object.keys(form.titleOptions) as (keyof TitleOptions)[]).map((key) => (
                <div key={key} className="space-y-2">
                  <Field label={key[0].toUpperCase() + key.slice(1)}>
                    <Textarea
                      value={form.titleOptions[key]}
                      readOnly={!editable}
                      onChange={(e) =>
                        update({ titleOptions: { ...form.titleOptions, [key]: e.target.value } })
                      }
                    />
                  </Field>
                  {editable && article.status !== 'APPROVED' && (
                    <Button
                      variant="outline"
                      disabled={dirty || title.isPending}
                      onClick={() => title.mutate({ key })}
                    >
                      {article.selectedTitleKey === key ? 'Selected' : `Select ${key} title`}
                    </Button>
                  )}
                </div>
              ))}
              {editable && article.status !== 'APPROVED' && (
                <form
                  className="space-y-2"
                  onSubmit={(e) => {
                    e.preventDefault()
                    title.mutate({ customTitle })
                  }}
                >
                  <Field label="Custom title">
                    <Input
                      maxLength={200}
                      value={customTitle}
                      onChange={(e) => setCustomTitle(e.target.value)}
                    />
                  </Field>
                  <Button variant="outline" disabled={dirty || title.isPending || !customTitle.trim()}>
                    Use custom title
                  </Button>
                </form>
              )}
            </TabsContent>
            <TabsContent value="seo" className="space-y-4">
              {form.seo ? (
                <>
                  {(
                    [
                      'seoTitle',
                      'metaDescription',
                      'slug',
                      'primaryKeyword',
                      'ogTitle',
                      'ogDescription',
                    ] as const
                  ).map((key) => (
                    <Field key={key} label={key.replace(/([A-Z])/g, ' $1')}>
                      <Input
                        readOnly={!editable}
                        value={form.seo![key]}
                        onChange={(e) => update({ seo: { ...form.seo!, [key]: e.target.value } })}
                      />
                    </Field>
                  ))}
                  <Field label="Secondary keywords (comma separated)">
                    <Input
                      readOnly={!editable}
                      value={form.seo.secondaryKeywords.join(', ')}
                      onChange={(e) =>
                        update({
                          seo: {
                            ...form.seo!,
                            secondaryKeywords: e.target.value.split(',').map((v) => v.trim()),
                          },
                        })
                      }
                    />
                  </Field>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">SEO has not been generated yet.</p>
              )}
              <Field label="Tags (comma separated)">
                <Input
                  value={form.tags.join(', ')}
                  readOnly={!editable}
                  onChange={(e) => {
                    const tags = e.target.value.split(',').map((v) => v.trim())
                    update({ tags, ...(form.seo ? { seo: { ...form.seo, tags } } : {}) })
                  }}
                />
              </Field>
              <Field label="Category">
                <Input
                  value={form.category}
                  readOnly={!editable}
                  onChange={(e) =>
                    update({
                      category: e.target.value,
                      ...(form.seo ? { seo: { ...form.seo, category: e.target.value } } : {}),
                    })
                  }
                />
              </Field>
              {article.social && (
                <div className="space-y-3">
                  <h3 className="font-medium">Social copy</h3>
                  {Object.entries(article.social).map(([key, value]) => (
                    <div key={key}>
                      <p className="text-sm font-medium">{key}</p>
                      <p className="whitespace-pre-wrap text-sm text-muted-foreground">{value}</p>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>
            <TabsContent value="versions">
              <VersionPanel articleId={article.id} currentVersionId={article.currentVersionId} />
            </TabsContent>
            <TabsContent value="publish">
              <PublishPanel article={article} />
            </TabsContent>
          </Tabs>
          {editable && ['edit', 'headline', 'seo'].includes(activeTab) && (
            <div className="mt-4 flex items-center gap-3 rounded-md border bg-background p-3">
              <Button disabled={!dirty || save.isPending || !baseVersionId} onClick={() => save.mutate()}>
                {save.isPending ? 'Saving…' : 'Save'}
              </Button>
              {dirty && (
                <>
                  <span className="text-xs text-muted-foreground">Unsaved changes</span>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      if (window.confirm('Discard your unsaved edits?')) reset(article)
                    }}
                  >
                    Discard edits
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
export function ArticleReviewPage() {
  const { articleId = '' } = useParams(),
    article = useQuery(articleQueryOptions(articleId))
  return (
    <section className="space-y-5">
      <PageHeading
        title="Article review"
        description="Review evidence, refine the article and approve a version for publication."
      />
      <QueryState query={article} label="article">
        {article.data && <Editor key={articleId} article={article.data} />}
      </QueryState>
    </section>
  )
}
