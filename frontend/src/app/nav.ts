import { type Permission, hasPermission } from '@/features/auth/permissions'
import type { SessionUser } from '@/features/auth/session'

export type NavItem = {
  label: string
  path: string
  permission: Permission
}

export const NAV_ITEMS: readonly NavItem[] = [
  { label: 'Dashboard', path: '/', permission: 'blog.view' },
  { label: 'Research', path: '/research', permission: 'blog.view' },
  { label: 'Drafts', path: '/drafts', permission: 'blog.view' },
  { label: 'Review Queue', path: '/review', permission: 'blog.review' },
  { label: 'Published', path: '/published', permission: 'blog.view' },
  { label: 'Generate', path: '/topics', permission: 'blog.view' },
  { label: 'Sources', path: '/sources', permission: 'blog.view' },
  { label: 'Settings', path: '/settings', permission: 'blog.settings' },
]

export function visibleNavItems(user: SessionUser | undefined): NavItem[] {
  return NAV_ITEMS.filter((item) => hasPermission(user, item.permission))
}

export const ARTICLE_REVIEW_PATH = '/articles/:articleId'
