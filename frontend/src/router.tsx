import type { ReactNode } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { type LoaderFunctionArgs, Navigate, type RouteObject, redirect } from 'react-router'
import { NAV_ITEMS, type NavItem } from '@/app/nav'
import { sessionQueryOptions } from '@/features/auth/session'
import { ApiError } from '@/lib/api'
import { AgentRunsPage } from '@/routes/agent-runs-page'
import { AppLayout } from '@/routes/app-layout'
import { DashboardPage } from '@/routes/dashboard-page'
import { LoginPage } from '@/routes/login-page'
import { PlaceholderPage } from '@/routes/placeholder-page'
import { RequirePermission } from '@/routes/require-permission'

export function requireSession(client: QueryClient) {
  return async ({ request }: LoaderFunctionArgs) => {
    try {
      await client.ensureQueryData(sessionQueryOptions)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        const url = new URL(request.url)
        throw redirect(`/login?next=${encodeURIComponent(url.pathname + url.search)}`)
      }
      throw error
    }
    return null
  }
}

function pageFor(item: NavItem): ReactNode {
  switch (item.path) {
    case '/':
      return <DashboardPage />
    case '/agent-runs':
      return <AgentRunsPage />
    default:
      return <PlaceholderPage title={item.label} />
  }
}

function navRoute(item: NavItem): RouteObject {
  const element = <RequirePermission permission={item.permission}>{pageFor(item)}</RequirePermission>
  return item.path === '/' ? { index: true, element } : { path: item.path.slice(1), element }
}

export function buildRoutes(client: QueryClient): RouteObject[] {
  return [
    { path: '/login', element: <LoginPage /> },
    {
      path: '/',
      loader: requireSession(client),
      element: <AppLayout />,
      hydrateFallbackElement: <p className="p-4 text-muted-foreground">Loading...</p>,
      children: NAV_ITEMS.map(navRoute),
    },
    // Unknown paths go to the dashboard; the session loader then applies.
    { path: '*', element: <Navigate to="/" replace /> },
  ]
}
