import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { articleSourcesQueryOptions, packetsQueryOptions } from '@/features/articles/api'
import { topicRoundQueryOptions } from '@/features/topics/api'
import { ExternalLink, QueryState, StatusBadge } from '@/features/shared/ui'
import { formatDate } from '@/features/shared/helpers'
import type { ArticleDetailOut } from '@/lib/types'

export function EvidencePanel({ article }: { article: ArticleDetailOut }) {
  const sources = useQuery(articleSourcesQueryOptions(article.id)),
    packets = useQuery(packetsQueryOptions(article.id)),
    topics = useQuery(topicRoundQueryOptions(article.runId))
  return (
    <Tabs defaultValue="quality">
      <TabsList aria-label="Evidence" className="flex h-auto flex-wrap justify-start">
        {['topic', 'research', 'sources', 'claims', 'quality', 'summary'].map((tab) => (
          <TabsTrigger key={tab} value={tab}>
            {tab[0].toUpperCase() + tab.slice(1)}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="topic" className="space-y-3">
        <QueryState query={topics} label="topic candidates">
          {topics.data?.items.map((topic) => (
            <div
              key={topic.id}
              className={`space-y-2 rounded-md border p-3 ${topic.id === article.candidateId ? 'border-primary bg-primary/5' : ''}`}
            >
              <p className="font-medium">
                {topic.title} {topic.id === article.candidateId && <Badge>Selected</Badge>}
              </p>
              <p className="text-sm">{topic.whyNow}</p>
              <p className="text-sm text-muted-foreground">{topic.mdcopilotConnection}</p>
              <p className="text-xs">
                Evidence {topic.evidenceScore?.toFixed(2) ?? '—'} · Novelty{' '}
                {topic.noveltyScore?.toFixed(2) ?? '—'} · Total {topic.totalScore?.toFixed(2) ?? '—'}
              </p>
            </div>
          ))}
          <Link
            className="inline-block text-sm underline"
            to={`/ideas?runId=${encodeURIComponent(article.runId)}`}
          >
            Change topic
          </Link>
        </QueryState>
      </TabsContent>
      <TabsContent value="research">
        <QueryState query={packets} label="research packets">
          {!packets.data?.length && (
            <p className="text-sm text-muted-foreground">Research is not available yet.</p>
          )}
          {packets.data?.map((packet) => (
            <details
              key={packet.id}
              open={packet.id === article.researchPacketId}
              className="mb-3 rounded-md border p-3"
            >
              <summary className="cursor-pointer font-medium">
                Research v{packet.version} · {formatDate(packet.createdAt)}
              </summary>
              <div className="mt-3 space-y-3 text-sm">
                <p>{packet.summary}</p>
                <h3 className="font-medium">Key facts</h3>
                {packet.packet.keyFacts.map((f, i) => (
                  <p key={i}>
                    {f.statement} <span className="text-muted-foreground">{f.markers.join(', ')}</span>
                  </p>
                ))}
                <h3 className="font-medium">Statistics</h3>
                {packet.packet.statistics.map((f, i) => (
                  <p key={i}>
                    {f.statement}: {f.value} ({f.asOf ?? 'date unknown'}) · {f.markers.join(', ')}
                  </p>
                ))}
                <h3 className="font-medium">Counterarguments</h3>
                {packet.packet.counterarguments.map((f, i) => (
                  <p key={i}>
                    {f.statement} · {f.markers.join(', ')}
                  </p>
                ))}
                <p>{packet.packet.industryContext}</p>
                <p>{packet.packet.mdcopilotConnection}</p>
                {packet.packet.claimsNeedingVerification.map((claim, i) => (
                  <p key={i} className="text-amber-700">
                    Verify: {claim}
                  </p>
                ))}
              </div>
            </details>
          ))}
        </QueryState>
      </TabsContent>
      <TabsContent value="sources">
        <QueryState query={sources} label="article sources">
          {!sources.data?.length && <p className="text-sm text-muted-foreground">No sources yet.</p>}
          {sources.data?.map((source) => (
            <div
              key={source.marker}
              id={`source-${source.marker}`}
              className="mb-3 space-y-2 rounded-md border p-3 text-sm"
            >
              <div className="flex gap-2">
                <Badge variant="outline">{source.marker}</Badge>
                <Badge variant="secondary">Tier {source.tier}</Badge>
                {source.isPrimary && <Badge>Primary</Badge>}
              </div>
              <ExternalLink href={source.url}>{source.title}</ExternalLink>
              <p className="text-muted-foreground">
                {source.publisher} · {formatDate(source.publishedAt)} ·{' '}
                {source.accessMode.replaceAll('_', ' ')}
              </p>
              <p className="text-xs">Date from {source.dateSource}</p>
            </div>
          ))}
        </QueryState>
      </TabsContent>
      <TabsContent value="claims" className="space-y-3">
        {article.factCheck ? (
          <>
            <div className="flex gap-2">
              <StatusBadge value={article.factCheck.verdict} />
              <Badge variant="outline">
                {article.factCheck.independentCheck ? 'Independent check' : 'Same-provider check'}
              </Badge>
            </div>
            {article.factCheck.claims.map((claim, i) => (
              <div className="space-y-2 rounded-md border p-3 text-sm" key={i}>
                <StatusBadge value={claim.verificationStatus} />
                <p className="font-medium">{claim.claim}</p>
                <p className="text-muted-foreground">
                  {claim.kind.replaceAll('_', ' ')} · {claim.sectionKey} ·{' '}
                  {(claim.confidence * 100).toFixed(0)}% confidence
                </p>
                <div className="flex gap-2">
                  {claim.citationMarkers.map((m) => (
                    <span key={m} className="rounded bg-muted px-2 py-1 text-xs">
                      {m}
                    </span>
                  ))}
                </div>
                {claim.recommendedRevision && (
                  <p className="text-amber-700">Suggested revision: {claim.recommendedRevision}</p>
                )}
              </div>
            ))}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">This version has not been fact checked.</p>
        )}
      </TabsContent>
      <TabsContent value="quality" className="space-y-3">
        <p className="text-sm">
          {article.recheckRequired
            ? 'Re-check required after edits.'
            : article.gatesPassedOnCurrentVersion
              ? 'Quality gates passed on this version.'
              : 'Quality checks have not passed on this version.'}
        </p>
        {article.qualityGates?.results.map((gate) => (
          <div key={gate.gate} className="rounded-md border p-3 text-sm">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="font-medium">{gate.gate.replaceAll('_', ' ')}</span>
              <Badge
                variant={gate.passed ? 'secondary' : gate.severity === 'blocking' ? 'destructive' : 'outline'}
              >
                {gate.passed ? 'Passed' : gate.severity}
              </Badge>
            </div>
            <p className="text-muted-foreground">{gate.details}</p>
          </div>
        ))}
        {!article.qualityGates && <p className="text-sm text-muted-foreground">No gate report yet.</p>}
      </TabsContent>
      <TabsContent value="summary" className="space-y-4 text-sm">
        <div>
          <h3 className="font-medium">Clinical review</h3>
          <p>{article.clinicalReview?.summary ?? 'Not reviewed yet.'}</p>
          {article.clinicalReview?.flags.map((flag, i) => (
            <p key={i} className={flag.severity === 'BLOCKING' ? 'text-destructive' : 'text-amber-700'}>
              {flag.severity}: {flag.message} ({flag.location})
            </p>
          ))}
        </div>
        <div>
          <h3 className="font-medium">Editorial review</h3>
          {article.editorialReview ? (
            <>
              <p>Score: {(article.editorialReview.editorialScore * 100).toFixed(0)}%</p>
              <p>{article.editorialReview.finalRecommendation}</p>
              {article.editorialReview.strengths.map((s, i) => (
                <p key={i}>Strength: {s}</p>
              ))}
              {article.editorialReview.weaknesses.map((s, i) => (
                <p key={i}>Issue: {s}</p>
              ))}
              {article.editorialReview.requiredChanges.map((c) => (
                <p key={c.id} className="text-amber-700">
                  Required: {c.description} ({c.location})
                </p>
              ))}
            </>
          ) : (
            <p>Not reviewed yet.</p>
          )}
        </div>
        {article.novelty && (
          <div>
            <h3 className="font-medium">Novelty</h3>
            <p>
              {article.novelty.decision} · {(article.novelty.maxSimilarity * 100).toFixed(0)}% maximum
              similarity
            </p>
            {article.novelty.neighbours.map((n) => (
              <p key={n.refId}>
                {n.title} · {(n.similarity * 100).toFixed(0)}%
              </p>
            ))}
          </div>
        )}
      </TabsContent>
    </Tabs>
  )
}
