import { useRouteError } from 'react-router'
import { Button } from '@/components/ui/button'
export function RouteErrorPage() {
  useRouteError()
  return (
    <main className="mx-auto max-w-lg space-y-4 p-8">
      <h1 className="text-xl font-semibold">This page could not be loaded</h1>
      <p className="text-sm text-muted-foreground">
        Check your connection and try again. Your saved work is still available.
      </p>
      <Button onClick={() => window.location.reload()}>Reload page</Button>
      <Button asChild variant="outline">
        <a href="/">Back to dashboard</a>
      </Button>
    </main>
  )
}
