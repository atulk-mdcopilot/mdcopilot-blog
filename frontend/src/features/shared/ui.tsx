import { describeProblem } from './helpers'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'

export function QueryState({
  query,
  label,
  children,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown }
  label: string
  children: ReactNode
}) {
  if (query.isPending) return <Skeleton className="h-36 w-full" aria-label={`Loading ${label}`} />
  if (query.isError)
    return (
      <div role="alert" className="rounded-md border border-destructive/30 p-4 text-sm">
        <p>
          Could not load {label}: {describeProblem(query.error)}
        </p>
        <Button className="mt-3" variant="outline" onClick={() => void query.refetch()}>
          Try again
        </Button>
      </div>
    )
  return <>{children}</>
}
export function PageHeading({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="font-heading text-2xl font-semibold">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {children}
    </div>
  )
}
export function StatusBadge({ value }: { value: string }) {
  return (
    <Badge
      variant={
        /FAIL|REJECT|UNSUPPORTED|MISLEADING/i.test(value)
          ? 'destructive'
          : /PASS|SUCCEEDED|PUBLISHED|SUPPORTED/i.test(value)
            ? 'default'
            : 'secondary'
      }
    >
      {value.replaceAll('_', ' ')}
    </Badge>
  )
}
export function Pagination({
  offset,
  limit = 20,
  total,
  onChange,
}: {
  offset: number
  limit?: number
  total: number
  onChange: (offset: number) => void
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
      <span>{total ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}` : 'No results'}</span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Previous page
        </Button>
        <Button variant="outline" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>
          Next page
        </Button>
      </div>
    </div>
  )
}
export function ExternalLink({ href, children }: { href: string | null; children: ReactNode }) {
  return href && /^https?:\/\//i.test(href) ? (
    <a
      className="text-primary underline underline-offset-4"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ) : (
    <span>{children}</span>
  )
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm font-medium">
      {label}
      {children}
    </label>
  )
}
