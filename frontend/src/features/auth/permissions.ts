import type { SessionUser } from '@/features/auth/session'

// Mirrors backend domain/enums.py Role and Permission values.
export type Role = 'viewer' | 'editor' | 'reviewer' | 'publisher' | 'admin'

export type Permission =
  | 'blog.view'
  | 'blog.generate'
  | 'blog.edit'
  | 'blog.review'
  | 'blog.approve'
  | 'blog.schedule'
  | 'blog.publish'
  | 'blog.agent_runs'
  | 'blog.settings'

// UI hint only. The API enforces every permission itself (deny by default).
export function hasPermission(user: SessionUser | undefined, permission: Permission): boolean {
  return user?.permissions.includes(permission) ?? false
}
