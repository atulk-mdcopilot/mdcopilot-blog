import { describe, expect, it } from 'vitest'
import { NAV_ITEMS, visibleNavItems } from '@/app/nav'
import { type Role, hasPermission } from '@/features/auth/permissions'
import { sessionFor } from '@/test/helpers'

function labelsFor(role: Role): string[] {
  return visibleNavItems(sessionFor(role).user).map((item) => item.label)
}

describe('NAV_ITEMS', () => {
  it('lists the spec pages in order with their paths and permissions', () => {
    expect(NAV_ITEMS.map((item) => [item.label, item.path, item.permission])).toEqual([
      ['Dashboard', '/', 'blog.view'],
      ["Today's Ideas", '/ideas', 'blog.view'],
      ['Research', '/research', 'blog.view'],
      ['Drafts', '/drafts', 'blog.view'],
      ['Review Queue', '/review', 'blog.review'],
      ['Published', '/published', 'blog.view'],
      ['Topics', '/topics', 'blog.view'],
      ['Content Calendar', '/calendar', 'blog.view'],
      ['Sources', '/sources', 'blog.view'],
      ['Settings', '/settings', 'blog.settings'],
      ['Agent Runs', '/agent-runs', 'blog.agent_runs'],
    ])
  })
})

describe('visibleNavItems', () => {
  it('shows a viewer the 8 view-only pages', () => {
    const labels = labelsFor('viewer')

    expect(labels).toHaveLength(8)
    expect(labels).not.toContain('Review Queue')
    expect(labels).not.toContain('Settings')
    expect(labels).not.toContain('Agent Runs')
  })

  it('shows an editor the same 8 pages', () => {
    expect(labelsFor('editor')).toEqual(labelsFor('viewer'))
  })

  it('adds Review Queue and Agent Runs for reviewers and publishers', () => {
    for (const role of ['reviewer', 'publisher'] as const) {
      const labels = labelsFor(role)
      expect(labels).toHaveLength(10)
      expect(labels).toContain('Review Queue')
      expect(labels).toContain('Agent Runs')
      expect(labels).not.toContain('Settings')
    }
  })

  it('shows an admin all 11 pages', () => {
    expect(labelsFor('admin')).toEqual(NAV_ITEMS.map((item) => item.label))
  })

  it('shows nothing without a session', () => {
    expect(visibleNavItems(undefined)).toEqual([])
  })
})

describe('hasPermission', () => {
  it('reads the permission list the server sent', () => {
    expect(hasPermission(sessionFor('editor').user, 'blog.generate')).toBe(true)
    expect(hasPermission(sessionFor('viewer').user, 'blog.generate')).toBe(false)
    expect(hasPermission(undefined, 'blog.view')).toBe(false)
  })
})
