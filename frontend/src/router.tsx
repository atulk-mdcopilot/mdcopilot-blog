import { RouteErrorPage } from '@/routes/route-error-page'
import type { ReactNode } from 'react'
import type { QueryClient } from '@tanstack/react-query'
import { type LoaderFunctionArgs, Navigate, type RouteObject, redirect } from 'react-router'
import { ARTICLE_REVIEW_PATH, NAV_ITEMS, type NavItem } from '@/app/nav'
import { sessionQueryOptions } from '@/features/auth/session'
import { ApiError } from '@/lib/api'
import { RunsPage } from '@/routes/runs-page'
import { ArticleList } from '@/features/articles/article-list'
import { AppLayout } from '@/routes/app-layout'
import { ArticleReviewPage } from '@/routes/article-review-page'
import { DashboardPage } from '@/routes/dashboard-page'
import { IdeasPage } from '@/routes/ideas-page'
import { LoginPage } from '@/routes/login-page'
import { RequirePermission } from '@/routes/require-permission'
import { ResearchPage } from '@/routes/research-page'
import { SettingsPage } from '@/routes/settings-page'
import { SourcesPage } from '@/routes/sources-page'
import { TopicsPage } from '@/routes/topics-page'

function requireSession(client: QueryClient) {
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
    case '/research':
      return <ResearchPage />
    case '/drafts':
      return (
        <ArticleList
          view="drafts"
          title="Drafts"
          description="Articles in production and drafts that need attention."
        />
      )
    case '/review':
      return (
        <ArticleList
          view="review"
          title="Review Queue"
          description="Review evidence and quality checks before approving an article."
        />
      )
    case '/published':
      return (
        <ArticleList
          view="published"
          title="Published"
          description="Approved, scheduled, exported and published articles."
        />
      )
    case '/topics':
      return <TopicsPage />
    case '/sources':
      return <SourcesPage />
    case '/settings':
      return <SettingsPage />
    default:
      return null
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
      errorElement: <RouteErrorPage />,
      hydrateFallbackElement: <p className="p-4 text-muted-foreground">Loading...</p>,
      children: [
        ...NAV_ITEMS.map(navRoute),
        {
          path: 'ideas',
          element: (
            <RequirePermission permission="blog.view">
              <IdeasPage />
            </RequirePermission>
          ),
        },
        {
          path: 'runs',
          element: (
            <RequirePermission permission="blog.agent_runs">
              <RunsPage />
            </RequirePermission>
          ),
        },
        {
          path: ARTICLE_REVIEW_PATH.slice(1),
          element: (
            <RequirePermission permission="blog.view">
              <ArticleReviewPage />
            </RequirePermission>
          ),
        },
      ],
    },
    // Unknown paths go to the dashboard; the session loader then applies.
    { path: '*', element: <Navigate to="/" replace /> },
  ]
}
