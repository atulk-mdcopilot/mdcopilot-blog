import { type Permission, hasPermission } from '@/features/auth/permissions'
import type { SessionUser } from '@/features/auth/session'

export type NavItem = {
  label: string
  path: string
  permission: Permission
}

// Spec §25 navigation, in display order.
export const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Dashboard', path: '/', permission: 'blog.view' },
  { label: "Today's Ideas", path: '/ideas', permission: 'blog.view' },
  { label: 'Research', path: '/research', permission: 'blog.view' },
  { label: 'Drafts', path: '/drafts', permission: 'blog.view' },
  { label: 'Review Queue', path: '/review', permission: 'blog.review' },
  { label: 'Published', path: '/published', permission: 'blog.view' },
  { label: 'Topics', path: '/topics', permission: 'blog.view' },
  { label: 'Content Calendar', path: '/calendar', permission: 'blog.view' },
  { label: 'Sources', path: '/sources', permission: 'blog.view' },
  { label: 'Settings', path: '/settings', permission: 'blog.settings' },
  { label: 'Agent Runs', path: '/agent-runs', permission: 'blog.agent_runs' },
]

export function visibleNavItems(user: SessionUser | undefined): NavItem[] {
  return NAV_ITEMS.filter((item) => hasPermission(user, item.permission))
}
