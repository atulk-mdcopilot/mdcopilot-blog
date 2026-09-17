import { Link } from 'react-router'
import { Button } from '@/components/ui/button'

export function ForbiddenPage() {
  return (
    <section className="flex flex-col items-start gap-3">
      <h1 className="font-heading text-2xl font-semibold">Access denied</h1>
      <p className="text-sm text-muted-foreground">
        Your role does not include this page. Ask an admin if you need access.
      </p>
      <Button asChild variant="outline">
        <Link to="/">Back to dashboard</Link>
      </Button>
    </section>
  )
}
