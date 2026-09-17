import { type FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { login, sessionQueryOptions } from '@/features/auth/session'
import { ApiError, problemMessage } from '@/lib/api'

// Only allow same-origin paths, to avoid open redirects. The value is parsed the way the browser
// will parse it: '/\evil.example' and tab/newline variants resolve to '//evil.example', so a
// plain startsWith('/') check is not enough.
function safeNextPath(raw: string | null): string {
  if (!raw) {
    return '/'
  }
  try {
    const url = new URL(raw, window.location.origin)
    const path = url.pathname + url.search + url.hash
    // '/.//evil.example' stays on this origin with the pathname '//evil.example', which the
    // history API would then read as a protocol-relative (off-site) URL.
    if (url.origin !== window.location.origin || path.startsWith('//')) {
      return '/'
    }
    return path
  } catch {
    return '/'
  }
}

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: async (session) => {
      queryClient.setQueryData(sessionQueryOptions.queryKey, session)
      await navigate(safeNextPath(searchParams.get('next')), { replace: true })
    },
    onError: (error) => {
      const message =
        error instanceof ApiError && error.status === 401
          ? 'Invalid email or password'
          : problemMessage(error, 'Sign-in failed, please try again')
      toast.error(message)
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    mutation.mutate({ email, password })
  }

  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <CardHeader>
            <CardTitle>
              <h1>Sign in</h1>
            </CardTitle>
            <CardDescription>Use your MDCopilot Blog account.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? 'Signing in...' : 'Sign in'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </main>
  )
}
