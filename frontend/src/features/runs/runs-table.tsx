import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { type RunOut, type RunStatus, formatCost } from '@/features/runs/api'

type BadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline'

function statusVariant(status: RunStatus): BadgeVariant {
  switch (status) {
    case 'SUCCEEDED':
      return 'default'
    case 'FAILED':
      return 'destructive'
    case 'CANCELLED':
      return 'outline'
    default:
      return 'secondary'
  }
}

type RunsTableProps = {
  runs: RunOut[] | undefined
  isPending: boolean
  isError: boolean
  showRunId?: boolean
  renderActions?: (run: RunOut) => ReactNode
}

export function RunsTable({ runs, isPending, isError, showRunId = false, renderActions }: RunsTableProps) {
  if (isPending) {
    return <Skeleton className="h-24 w-full" aria-label="Loading runs" />
  }
  if (isError) {
    return <p className="text-sm text-destructive">Could not load runs.</p>
  }
  if (!runs || runs.length === 0) {
    return <p className="text-sm text-muted-foreground">No runs yet.</p>
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {showRunId ? <TableHead>Run</TableHead> : null}
          <TableHead>Status</TableHead>
          <TableHead>Kind</TableHead>
          <TableHead>Date</TableHead>
          <TableHead className="text-right">Cost</TableHead>
          {renderActions ? (
            <TableHead>
              <span className="sr-only">Actions</span>
            </TableHead>
          ) : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.id}>
            {showRunId ? (
              <TableCell className="font-mono text-xs" title={run.id}>
                {run.id.slice(0, 8)}
              </TableCell>
            ) : null}
            <TableCell>
              <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
            </TableCell>
            <TableCell>{run.kind}</TableCell>
            <TableCell>{run.runDate}</TableCell>
            <TableCell className="text-right tabular-nums">{formatCost(run.costUsd)}</TableCell>
            {renderActions ? <TableCell className="text-right">{renderActions(run)}</TableCell> : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
