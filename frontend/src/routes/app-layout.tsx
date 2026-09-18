import { type ReactNode, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ClipboardCheckIcon,
  FileTextIcon,
  FlaskConicalIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  LightbulbIcon,
  MenuIcon,
  SendIcon,
  SettingsIcon,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { type NavItem, visibleNavItems } from '@/app/nav'
import { logout, sessionQueryOptions } from '@/features/auth/session'
import { cn } from 'cn'

const ICON_CLASS = 'size-4'

const NAV_ICONS: Record<string, ReactNode> = {
  '/': <LayoutDashboardIcon className={ICON_CLASS} aria-hidden="true" />,
  '/topics': <LightbulbIcon className={ICON_CLASS} aria-hidden="true" />,
  '/research': <FlaskConicalIcon className={ICON_CLASS} aria-hidden="true" />,
  '/drafts': <FileTextIcon className={ICON_CLASS} aria-hidden="true" />,
  '/review': <ClipboardCheckIcon className={ICON_CLASS} aria-hidden="true" />,
  '/published': <SendIcon className={ICON_CLASS} aria-hidden="true" />,
  '/sources': <LibraryIcon className={ICON_CLASS} aria-hidden="true" />,
  '/settings': <SettingsIcon className={ICON_CLASS} aria-hidden="true" />,
}

type NavListProps = {
  items: NavItem[]
  onNavigate?: () => void
}

function NavList({ items, onNavigate }: NavListProps) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {items.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          end={item.path === '/'}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
              isActive
                ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
            )
          }
        >
          {NAV_ICONS[item.path]}
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

// The route loader (see router.tsx) guarantees a session is cached before this renders.
export function AppLayout() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: session } = useQuery(sessionQueryOptions)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const items = visibleNavItems(session?.user)
  useEffect(() => {
    let redirected = false
    const expire = () => {
      if (redirected) return
      redirected = true
      const next = window.location.pathname + window.location.search
      queryClient.clear()
      void navigate(`/login?next=${encodeURIComponent(next)}`, { replace: true })
    }
    window.addEventListener('mdcb:session-expired', expire)
    return () => window.removeEventListener('mdcb:session-expired', expire)
  }, [navigate, queryClient])

  async function handleLogout() {
    try {
      await logout()
    } catch {
      // The server session may already be gone (401); signing out locally is still correct.
    }
    queryClient.clear()
    await navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex h-14 items-center justify-between gap-2 border-b px-4">
        <div className="flex items-center gap-2">
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
                <MenuIcon />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64">
              <SheetHeader>
                <SheetTitle>MDCopilot Blog</SheetTitle>
                <SheetDescription>Go to a page.</SheetDescription>
              </SheetHeader>
              <div className="px-4">
                <NavList items={items} onNavigate={() => setMobileNavOpen(false)} />
              </div>
            </SheetContent>
          </Sheet>
          <span className="font-heading font-semibold">MDCopilot Blog</span>
        </div>
        <div className="flex items-center gap-2">
          {session ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline">{session.user.displayName}</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="flex flex-col gap-0.5">
                  <span className="truncate text-foreground">{session.user.email}</span>
                  <span className="capitalize">{session.user.role}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => void handleLogout()}>Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Skeleton className="h-8 w-32" />
          )}
        </div>
      </header>
      <div className="flex flex-1">
        <aside className="hidden w-60 shrink-0 border-r bg-sidebar p-3 md:block">
          <NavList items={items} />
        </aside>
        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
