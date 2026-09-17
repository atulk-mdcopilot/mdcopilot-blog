import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type Permission, hasPermission } from '@/features/auth/permissions'
import { sessionQueryOptions } from '@/features/auth/session'
import { ForbiddenPage } from '@/routes/forbidden-page'

type RequirePermissionProps = {
  permission: Permission
  children: ReactNode
}

// UI gate for pages opened directly by URL. The API enforces the same permission on its routes.
export function RequirePermission({ permission, children }: RequirePermissionProps) {
  const { data: session } = useQuery(sessionQueryOptions)
  if (!hasPermission(session?.user, permission)) {
    return <ForbiddenPage />
  }
  return children
}
