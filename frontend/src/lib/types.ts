// API response types use camelCase.

export type Page<T> = { items: T[]; total: number; limit: number; offset: number }

type ArticleStatus =
  | 'DRAFTING'
  | 'FACT_CHECKING'
  | 'CLINICAL_REVIEW'
  | 'EDITORIAL_REVIEW'
  | 'SEO'
  | 'READY_FOR_REVIEW'
  | 'QUALITY_GATE_FAILED'
  | 'APPROVED'
  | 'SCHEDULED'
  | 'EXPORTED'
  | 'PUBLISHING'
  | 'PUBLISHED'
  | 'PUBLISH_FAILED'
  | 'REJECTED'
  | 'FAILED'
  | 'SUPERSEDED'

export type RunStatus =
  | 'QUEUED'
  | 'RESEARCHING'
  | 'TOPICS_READY'
  | 'WAITING_FOR_TOPIC'
  | 'PRODUCING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED'

export interface TopicCandidateOut {
  id: string
  runId: string
  round: number
  position: number
  title: string
  hook: string
  whyNow: string
  thesis: string
  angle: string
  coreArgument: string
  mdcopilotConnection: string
  targetAudience: string
  pillar: string
  relevantNews: { title: string; url: string; publishedAt: string | null }[]
  sources: {
    id: string
    marker: string | null
    title: string
    url: string
    publisher: string
    domain: string
    tier: number
    publishedAt: string | null
    accessMode: string
  }[]
  examples: string[]
  noveltyScore: number | null
  evidenceScore: number | null
  businessRelevance: number | null
  editorialPotential: number | null
  timelinessScore: number | null
  audienceRelevance: number | null
  totalScore: number | null
  scoreBreakdown: Record<string, { weight: number; score: number; justification: string }>
  novelty: {
    decision: string
    maxSimilarity: number
    neighbours: { kind: string; refId: string; title: string; similarity: number }[]
  } | null
  status: string
  isManual: boolean
  selectedAt: string | null
  selectedBy: string | null
  rejectedReason: string | null
  articleId: string | null
  createdAt: string
  updatedAt: string
}

export interface TopicRoundOut {
  runId: string
  runStatus: RunStatus
  round: number
  roundsAvailable: number[]
  shortfall: boolean
  items: TopicCandidateOut[]
}

export interface ArticleSummaryOut {
  id: string
  runId: string
  runDate: string
  title: string | null
  slug: string | null
  status: ArticleStatus
  pipelineStatus: RunStatus
  pillar: string
  category: string
  currentVersionNo: number | null
  wordCount: number | null
  gateBadge: { passed: boolean | null; failedGates: string[]; recheckRequired: boolean }
  factCheckVerdict: 'PASS' | 'FAIL' | null
  independentCheck: boolean | null
  editorialScore: number | null
  scheduledFor: string | null
  publishedAt: string | null
  publishedUrl: string | null
  createdAt: string
  updatedAt: string
}

export interface ResearchRunOut {
  id: string
  runId: string
  articleId: string | null
  kind: string
  status: string
  pillar: string | null
  windowDays: number
  queries: {
    text: string
    themeKey: string | null
    status: string
    searchActions: number
    sourceCount: number
    error: string | null
  }[]
  themesCovered: string[]
  phaseLatencyMs: Record<string, number>
  counts: Record<string, number>
  sourceCount: number
  findingCount: number
  startedAt: string
  finishedAt: string | null
  error: Record<string, unknown> | null
  traceId: string
  createdAt: string
}

export interface LedgerSourceOut {
  id: string
  title: string
  url: string
  canonicalUrl: string
  publisher: string
  domain: string
  sourceType: string
  tier: number
  publishedAt: string | null
  dateSource: string
  retrievedAt: string
  accessMode: string
  fetchStatus: string
  wordCount: number
  isPreprint: boolean
  discoveredVia: string
  relevanceScore: number
}

interface FindingOut {
  id: string
  position: number
  claim: string
  evidence: string
  confidence: number
  category: string
  claimType: string
  importance: string
  isPreprint: boolean
  downgradedFrom: string | null
  sources: {
    id: string
    marker: string | null
    title: string
    url: string
    publisher: string
    domain: string
    tier: number
    publishedAt: string | null
    accessMode: string
  }[]
}

export interface ResearchRunDetail extends ResearchRunOut {
  findings: FindingOut[]
  sources: LedgerSourceOut[]
}

export interface SourceFeedOut {
  id: string
  name: string
  url: string
  kind: string
  group: string
  tier: number
  sourceType: string
  pillarKeys: string[]
  themeKeys: string[]
  headerProfile: string
  isEnabled: boolean
  isPreprint: boolean
  lastFetchedAt: string | null
  lastSuccessAt: string | null
  lastError: string | null
  consecutiveFailures: number
  disabledReason: string | null
  itemCountLast: number
}

export interface SourceDomainOut {
  id: string
  domain: string
  tier: number
  sourceType: string
  publisher: string | null
  headerProfile: string
  fetchPolicy: string
  verificationAllowlisted: boolean
  notes: string | null
}

export interface ThemeOut {
  id: string
  key: string
  name: string
  description: string
  queryTemplates: string[]
  pillarKeys: string[]
  isActive: boolean
  lastSearchedAt: string | null
  sortOrder: number
}

export interface ExternalPostOut {
  id: string
  origin: string
  slug: string
  title: string
  excerpt: string
  url: string
  publishedAt: string | null
  headlinePattern: string
  lastSyncedAt: string
}

export interface TopicHistoryOut {
  id: string
  title: string
  pillar: string
  thesis: string
  coreArgument: string
  headlinePattern: string
  keywords: string[]
  examples: string[]
  primarySourceUrl: string | null
  articleId: string | null
  articleStatus: ArticleStatus | null
  createdAt: string
}

interface DashboardMetricsOut {
  windowDays: number
  postsGenerated: number
  postsPublished: number
  postsPending: number
}

export interface TodayCardOut {
  date: string
  runId: string | null
  runStatus: RunStatus | null
  researchStatus: string
  opportunitiesDiscovered: number
  recommendedTopic: {
    candidateId: string
    title: string
    whyNow: string
    pillar: string
    evidenceScore: number | null
    businessRelevance: number | null
    noveltyScore: number | null
    totalScore: number | null
  } | null
  articleId: string | null
  articleStatus: ArticleStatus | null
  headlineOptions: { provocative: string; operational: string; visionary: string } | null
  quality: Record<string, unknown> | null
}

export interface DashboardOut {
  generatedAt: string
  timezone: string
  today: TodayCardOut
  pipeline: {
    runId: string | null
    stages: {
      key: string
      label: string
      status: string
      startedAt: string | null
      finishedAt: string | null
    }[]
  }
  metrics: DashboardMetricsOut
}

export interface PillarOut {
  id: string
  key: string
  name: string
  description: string
  topics: string[]
  weekdays: number[]
  isActive: boolean
  sortOrder: number
}

export interface SettingsOut {
  appVersion: string
  agentEnabled: boolean
  schedulerEnabled: boolean
  publishingEnabled: boolean
  humanApprovalRequired: boolean
  schedule: Record<string, string>
  routes: Record<string, string[]>
  limits: Record<string, string | number>
  publisher: string
  providers: Record<string, { configured: boolean; preview: string | null }>
  autoPublishAvailable: false
  version: number | null
  updatedAt: string | null
  updatedBy: string | null
  effective: Record<string, unknown>
  values: Record<string, unknown>
}

export interface ActionAccepted {
  workflowId: string
  workflowName: string
  queue: string
  runId: string
  articleId: string | null
  candidateId: string | null
}

export type TitleOptions = { provocative: string; operational: string; visionary: string }
type SeoMetadata = {
  seoTitle: string
  metaDescription: string
  slug: string
  primaryKeyword: string
  secondaryKeywords: string[]
  ogTitle: string
  ogDescription: string
  tags: string[]
  category: string
  internalLinkSuggestions: { title: string; url: string }[]
  externalReferences: string[]
}
type SocialCopy = { linkedin: string; xPost: string; newsletterTeaser: string }
type BlogSource = {
  marker: string
  sourceId: string
  title: string
  url: string
  publisher: string
  publishedAt: string | null
}
export type ArticleSourceOut = BlogSource & {
  canonicalUrl: string
  domain: string
  tier: number
  dateSource: string
  accessMode: string
  isPrimary: boolean
}
type ArticleSection = { key: string; heading: string | null; bodyMarkdown: string }
type ClaimCheck = {
  claim: string
  kind: string
  importance: string
  sectionKey: string
  sentenceIndex: number
  span: string
  citationMarkers: string[]
  sourceId: string | null
  verificationStatus: string
  confidence: number
  recommendedRevision: string | null
}
type GateReport = {
  passed: boolean
  results: { gate: string; passed: boolean; severity: string; details: string }[]
}
export interface ArticleDetailOut {
  id: string
  runId: string
  runDate: string
  topicId: string
  candidateId: string
  titleOptions: TitleOptions | null
  selectedTitle: string | null
  selectedTitleKey: string | null
  slug: string | null
  contentMarkdown: string | null
  sections: ArticleSection[] | null
  excerpt: string | null
  pullQuote: string | null
  cta: string | null
  category: string
  tags: string[]
  pillar: string
  seo: SeoMetadata | null
  social: SocialCopy | null
  sources: BlogSource[]
  researchSummary: string | null
  researchPacketId: string | null
  researchPacketVersion: number | null
  factCheck: { verdict: string; independentCheck: boolean; claims: ClaimCheck[] } | null
  clinicalReview: {
    flags: { code: string; severity: string; message: string; location: string }[]
    summary: string
  } | null
  editorialReview: {
    editorialScore: number
    strengths: string[]
    weaknesses: string[]
    requiredChanges: { id: string; description: string; location: string }[]
    optionalChanges: { id: string; description: string; location: string }[]
    finalRecommendation: string
  } | null
  qualityGates: GateReport | null
  novelty: TopicCandidateOut['novelty']
  status: ArticleStatus
  pipelineStatus: RunStatus
  versionNo: number | null
  currentVersionId: string | null
  approvedVersionId: string | null
  publishedVersionId: string | null
  recheckRequired: boolean
  gatesPassedOnCurrentVersion: boolean
  networkPublishingActive: boolean
  gateOverridePolicy: 'admin_with_reason' | 'never'
  approvedAt: string | null
  approvedBy: string | null
  approvalMode: 'draft' | 'publish' | null
  rejectionReason: string | null
  scheduledFor: string | null
  scheduledBy: string | null
  publishedAt: string | null
  publishedUrl: string | null
  createdAt: string
  updatedAt: string
}
export type ArticleEdit = {
  baseVersionId: string
  contentMarkdown?: string
  pullQuote?: string
  cta?: string
  excerpt?: string
  titleOptions?: TitleOptions
  seo?: Partial<Omit<SeoMetadata, 'internalLinkSuggestions' | 'externalReferences'>>
  tags?: string[]
  category?: string
}
export type VersionSummaryOut = {
  id: string
  versionNo: number
  parentVersionId: string | null
  changeKind: string
  changeScope: Record<string, unknown>
  wordCount: number
  createdBy: string | null
  createdByKind: string
  createdAt: string
  factCheckVerdict: string | null
  gatesPassed: boolean | null
}
export type VersionDetailOut = VersionSummaryOut & {
  titleOptions: TitleOptions
  contentMarkdown: string
  pullQuote: string
  cta: string
  excerpt: string
  sections: ArticleSection[]
  seo: SeoMetadata | null
  social: SocialCopy | null
}
export type VersionDiffOut = {
  fromVersionId: string
  toVersionId: string
  fromVersionNo: number
  toVersionNo: number
  unifiedDiff: string
  fieldChanges: { field: string; from: string | null; to: string | null }[]
}
export type ResearchPacketOut = {
  id: string
  articleId: string
  version: number
  summary: string
  packet: {
    summary: string
    keyFacts: { statement: string; markers: string[]; importance: string }[]
    statistics: { statement: string; value: string; markers: string[]; asOf: string | null }[]
    counterarguments: { statement: string; markers: string[] }[]
    industryContext: string
    mdcopilotConnection: string
    claimsNeedingVerification: string[]
  }
  sources: TopicCandidateOut['sources']
  researchRunId: string | null
  createdAt: string
}
export type PreviewOut = { versionId: string; html: string; issues: { field: string; message: string }[] }
export type ExportBundleOut = {
  publicationId: string
  articleId: string
  versionId: string
  title: string
  slug: string
  excerpt: string
  html: string
  text: string
  seo: SeoMetadata
  social: SocialCopy | null
  tags: string[]
  category: string
  references: BlogSource[]
  disclosure: string
  status: ArticleStatus
}
export type PublicationOut = {
  id: string
  versionId: string
  publisher: string
  target: string
  status: string
  externalPostId: string | null
  publishedUrl: string | null
  publishedAt: string | null
  asDraft: boolean
  attempts: number
  lastError: Record<string, unknown> | null
  createdAt: string
  updatedAt: string
}
