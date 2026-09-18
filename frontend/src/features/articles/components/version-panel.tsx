import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { diffQueryOptions, versionQueryOptions, versionsQueryOptions } from '@/features/articles/api'
import { Field, QueryState } from '@/features/shared/ui'
import { formatDate } from '@/features/shared/helpers'
export function VersionPanel({
  articleId,
  currentVersionId,
}: {
  articleId: string
  currentVersionId: string | null
}) {
  const versions = useQuery(versionsQueryOptions(articleId))
  const [from, setFrom] = useState(''),
    [to, setTo] = useState(currentVersionId ?? '')
  const diff = useQuery(diffQueryOptions(articleId, from, to)),
    snapshot = useQuery(versionQueryOptions(articleId, from))
  return (
    <div className="space-y-4">
      <QueryState query={versions} label="versions">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="From version">
            <select
              className="h-9 rounded border bg-background px-2"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            >
              <option value="">Choose version</option>
              {versions.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.versionNo} · {v.changeKind} · {formatDate(v.createdAt)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="To version">
            <select
              className="h-9 rounded border bg-background px-2"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            >
              <option value="">Choose version</option>
              {versions.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.versionNo} · {v.changeKind}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="mt-3 space-y-2">
          {versions.data?.map((v) => (
            <div key={v.id} className="rounded border p-3 text-sm">
              <p className="font-medium">
                Version {v.versionNo} · {v.changeKind.replaceAll('_', ' ')} · {v.createdByKind}
              </p>
              <p className="text-muted-foreground">
                {v.wordCount} words · {formatDate(v.createdAt)} · Fact check:{' '}
                {v.factCheckVerdict ?? 'pending'} · Gates:{' '}
                {v.gatesPassed === null ? 'pending' : v.gatesPassed ? 'passed' : 'failed'}
              </p>
            </div>
          ))}
        </div>
      </QueryState>
      {from && to && from !== to && (
        <QueryState query={diff} label="version diff">
          <div className="rounded border p-3 text-sm">
            <h3 className="mb-3 font-medium">
              Changes from v{diff.data?.fromVersionNo} to v{diff.data?.toVersionNo}
            </h3>
            <pre className="overflow-auto whitespace-pre-wrap text-xs">
              {diff.data?.unifiedDiff || 'Article text is unchanged.'}
            </pre>
            {diff.data?.fieldChanges.map((change) => (
              <div className="mt-3" key={change.field}>
                <p className="font-medium">{change.field}</p>
                <del className="block text-red-700">{change.from}</del>
                <ins className="block text-green-700">{change.to}</ins>
              </div>
            ))}
          </div>
        </QueryState>
      )}
      {from && (
        <QueryState query={snapshot} label="version snapshot">
          <details className="rounded border p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Read version {snapshot.data?.versionNo}
            </summary>
            <pre className="mt-3 whitespace-pre-wrap text-sm">{snapshot.data?.contentMarkdown}</pre>
          </details>
        </QueryState>
      )}
    </div>
  )
}
