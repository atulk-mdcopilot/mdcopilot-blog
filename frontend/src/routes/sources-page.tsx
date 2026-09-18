import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  domainsQueryOptions,
  feedsQueryOptions,
  sourcesQueryOptions,
  themesQueryOptions,
  updateDomain,
  updateFeed,
  updateThemes,
} from '@/features/sources/api'
import { ConfigFields } from '@/features/shared/config-fields'
import { ExternalLink, Field, PageHeading, Pagination, QueryState } from '@/features/shared/ui'
import { describeProblem, formatDate, useCan } from '@/features/shared/helpers'
import type { ThemeOut } from '@/lib/types'
function ThemesEditor({ items }: { items: ThemeOut[] }) {
  const canEdit = useCan('blog.settings'),
    client = useQueryClient()
  const [draft, setDraft] = useState(
    items.map(({ id: _id, lastSearchedAt: _last, ...theme }) => {
      void _id
      void _last
      return theme
    }),
  )
  const mutation = useMutation({
    mutationFn: () => updateThemes(draft),
    onSuccess: async () => {
      toast.success('Themes saved')
      await client.invalidateQueries({ queryKey: ['sources', 'themes'] })
    },
    onError: (e) => toast.error(describeProblem(e)),
  })
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        mutation.mutate()
      }}
    >
      {draft.map((theme, i) => (
        <details key={i} className="rounded border p-4">
          <summary className="cursor-pointer font-medium">
            {theme.name || 'New theme'} {theme.isActive ? '' : '(inactive)'}
          </summary>
          <div className="mt-4">
            <ConfigFields
              values={theme}
              disabled={!canEdit}
              onChange={(values) => setDraft(draft.map((t, j) => (j === i ? (values as typeof theme) : t)))}
            />
          </div>
        </details>
      ))}
      {canEdit && (
        <div className="flex gap-2">
          <Button disabled={mutation.isPending}>Save themes</Button>
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              setDraft([
                ...draft,
                {
                  key: '',
                  name: '',
                  description: '',
                  queryTemplates: [''],
                  pillarKeys: [],
                  isActive: true,
                  sortOrder: draft.length,
                },
              ])
            }
          >
            Add theme
          </Button>
        </div>
      )}
    </form>
  )
}
export function SourcesPage() {
  const client = useQueryClient(),
    canEdit = useCan('blog.settings')
  const feeds = useQuery(feedsQueryOptions()),
    domains = useQuery(domainsQueryOptions()),
    themes = useQuery(themesQueryOptions())
  const [filters, setFilters] = useState({ q: '', domain: '', accessMode: '', tier: '' }),
    [offset, setOffset] = useState(0)
  const recent = useQuery(
    sourcesQueryOptions(20, offset, {
      ...(filters.domain ? { domain: filters.domain } : {}),
      ...(filters.q ? { q: filters.q } : {}),
      ...(filters.accessMode ? { accessMode: filters.accessMode } : {}),
      ...(filters.tier ? { tier: Number(filters.tier) } : {}),
    }),
  )
  const [edit, setEdit] = useState<{
    kind: 'feed' | 'domain'
    id: string
    title: string
    values: Record<string, unknown>
  } | null>(null)
  const mutation = useMutation({
    mutationFn: (perform: () => Promise<unknown>) => perform(),
    onSuccess: async () => {
      setEdit(null)
      toast.success('Source configuration saved')
      await client.invalidateQueries({ queryKey: ['sources'] })
    },
    onError: (e) => toast.error(describeProblem(e)),
  })
  return (
    <section className="space-y-5">
      <PageHeading
        title="Sources"
        description="Browse evidence, monitor feed health and configure discovery rules."
      />
      <Tabs defaultValue="ledger">
        <TabsList className="h-auto flex-wrap">
          {['ledger', 'feeds', 'domains', 'themes'].map((tab) => (
            <TabsTrigger key={tab} value={tab}>
              {tab[0].toUpperCase() + tab.slice(1)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="ledger" className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Field label="Search title">
              <Input
                value={filters.q}
                onChange={(e) => {
                  setFilters({ ...filters, q: e.target.value })
                  setOffset(0)
                }}
              />
            </Field>
            <Field label="Domain">
              <Input
                value={filters.domain}
                onChange={(e) => {
                  setFilters({ ...filters, domain: e.target.value })
                  setOffset(0)
                }}
              />
            </Field>
            <Field label="Tier">
              <select
                className="h-9 rounded border bg-background px-2"
                value={filters.tier}
                onChange={(e) => {
                  setFilters({ ...filters, tier: e.target.value })
                  setOffset(0)
                }}
              >
                <option value="">All tiers</option>
                {[1, 2, 3].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </Field>
            <Field label="Access mode">
              <select
                className="h-9 rounded border bg-background px-2"
                value={filters.accessMode}
                onChange={(e) => {
                  setFilters({ ...filters, accessMode: e.target.value })
                  setOffset(0)
                }}
              >
                <option value="">All access modes</option>
                {['full_text', 'abstract_only', 'metadata_only'].map((mode) => (
                  <option key={mode}>{mode}</option>
                ))}
              </select>
            </Field>
          </div>
          <QueryState query={recent} label="source ledger">
            {!recent.data?.items.length && (
              <p className="text-sm text-muted-foreground">No sources match these filters.</p>
            )}
            {recent.data?.items.map((s) => (
              <div className="mb-3 space-y-2 rounded border p-4" key={s.id}>
                <ExternalLink href={s.url}>{s.title}</ExternalLink>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">Tier {s.tier}</Badge>
                  <Badge variant="secondary">{s.accessMode}</Badge>
                  {s.isPreprint && <Badge variant="outline">Preprint</Badge>}
                </div>
                <p className="text-sm text-muted-foreground">
                  {s.publisher} · {s.domain} · Published {formatDate(s.publishedAt)} ({s.dateSource}) ·{' '}
                  {s.wordCount} words
                </p>
                <p className="text-xs text-muted-foreground">
                  Retrieved {formatDate(s.retrievedAt)} · {s.fetchStatus} · {s.discoveredVia}
                </p>
              </div>
            ))}
            <Pagination offset={offset} total={recent.data?.total ?? 0} onChange={setOffset} />
          </QueryState>
        </TabsContent>
        <TabsContent value="feeds">
          <QueryState query={feeds} label="feed health">
            {feeds.data?.map((f) => (
              <div key={f.id} className="mb-3 flex flex-wrap justify-between gap-3 rounded border p-4">
                <div className="space-y-2">
                  <ExternalLink href={f.url}>{f.name}</ExternalLink>
                  <p className="text-sm">
                    {f.group} · Tier {f.tier} · {f.isEnabled ? 'Enabled' : 'Disabled'} ·{' '}
                    {f.consecutiveFailures} consecutive failures
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Last success {formatDate(f.lastSuccessAt)} · {f.itemCountLast} items
                  </p>
                  {(f.lastError || f.disabledReason) && (
                    <p className="text-sm text-destructive">{f.disabledReason ?? f.lastError}</p>
                  )}
                </div>
                {canEdit && (
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={mutation.isPending}
                      onClick={() => mutation.mutate(() => updateFeed(f.id, { isEnabled: !f.isEnabled }))}
                    >
                      {f.isEnabled ? 'Disable' : 'Enable'} feed
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setEdit({
                          kind: 'feed',
                          id: f.id,
                          title: f.name,
                          values: {
                            isEnabled: f.isEnabled,
                            tier: f.tier,
                            headerProfile: f.headerProfile,
                            pillarKeys: f.pillarKeys,
                            themeKeys: f.themeKeys,
                          },
                        })
                      }
                    >
                      Edit feed
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </QueryState>
        </TabsContent>
        <TabsContent value="domains">
          <QueryState query={domains} label="domain rules">
            {domains.data?.map((d) => (
              <div key={d.id} className="mb-3 flex flex-wrap justify-between gap-3 rounded border p-4">
                <div>
                  <p className="font-medium">{d.domain}</p>
                  <p className="text-sm text-muted-foreground">
                    Tier {d.tier} · {d.sourceType} · {d.fetchPolicy} · Verification{' '}
                    {d.verificationAllowlisted ? 'allowed' : 'not allowlisted'}
                  </p>
                  <p className="text-sm">{d.notes}</p>
                </div>
                {canEdit && (
                  <Button
                    variant="outline"
                    onClick={() =>
                      setEdit({
                        kind: 'domain',
                        id: d.id,
                        title: d.domain,
                        values: {
                          tier: d.tier,
                          sourceType: d.sourceType,
                          publisher: d.publisher ?? '',
                          headerProfile: d.headerProfile,
                          fetchPolicy: d.fetchPolicy,
                          verificationAllowlisted: d.verificationAllowlisted,
                          notes: d.notes ?? '',
                        },
                      })
                    }
                  >
                    Edit domain
                  </Button>
                )}
              </div>
            ))}
          </QueryState>
        </TabsContent>
        <TabsContent value="themes">
          <QueryState query={themes} label="themes">
            {themes.data && <ThemesEditor key={JSON.stringify(themes.data)} items={themes.data} />}
          </QueryState>
        </TabsContent>
      </Tabs>
      <Dialog open={!!edit} onOpenChange={(open) => !open && setEdit(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit {edit?.title}</DialogTitle>
            <DialogDescription>Changes apply to future discovery and verification.</DialogDescription>
          </DialogHeader>
          {edit && <ConfigFields values={edit.values} onChange={(values) => setEdit({ ...edit, values })} />}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEdit(null)}>
              Cancel
            </Button>
            <Button
              disabled={mutation.isPending}
              onClick={() =>
                edit &&
                mutation.mutate(() =>
                  edit.kind === 'feed'
                    ? updateFeed(edit.id, edit.values)
                    : updateDomain(edit.id, edit.values),
                )
              }
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
