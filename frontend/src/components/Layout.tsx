/** The frame: a sidebar on a wide screen, a drawer on a narrow one. */

import {
  Boxes,
  Cog,
  Download,
  Home,
  LogOut,
  MapPinned,
  Menu,
  Moon,
  QrCode,
  Package,
  Receipt,
  Search,
  Settings,
  Sun,
  Cable,
  Tags,
  Wrench,
  HandHelping,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { cx } from '@/lib/format'
import { useAuthStore } from '@/store/auth'
import { useUiStore } from '@/store/ui'
import { Button } from './ui'
import Toaster from './Toaster'

const NAV: Array<{ to: string; label: string; icon: ReactNode }> = [
  { to: '/', label: 'Dashboard', icon: <Home className="h-4 w-4" /> },
  { to: '/items', label: 'Items', icon: <Boxes className="h-4 w-4" /> },
  { to: '/locations', label: 'Locations', icon: <MapPinned className="h-4 w-4" /> },
  { to: '/receipts', label: 'Receipts', icon: <Receipt className="h-4 w-4" /> },
  { to: '/tags', label: 'Tags', icon: <Tags className="h-4 w-4" /> },
  { to: '/components', label: 'Components', icon: <Cog className="h-4 w-4" /> },
  { to: '/spares', label: 'Spares', icon: <Package className="h-4 w-4" /> },
  { to: '/cables', label: 'Cables', icon: <Cable className="h-4 w-4" /> },
  { to: '/maintenance', label: 'Maintenance', icon: <Wrench className="h-4 w-4" /> },
  { to: '/lending', label: 'Lending', icon: <HandHelping className="h-4 w-4" /> },
  { to: '/labels', label: 'Labels', icon: <QrCode className="h-4 w-4" /> },
  { to: '/export', label: 'Export', icon: <Download className="h-4 w-4" /> },
  { to: '/settings', label: 'Settings', icon: <Settings className="h-4 w-4" /> },
]

export default function Layout() {
  const navigate = useNavigate()
  const { theme, toggleTheme, sidebarOpen, setSidebar, search, setSearch } = useUiStore()
  const user = useAuthStore((state) => state.user)
  const signOut = useAuthStore((state) => state.signOut)
  const [term, setTerm] = useState(search)

  useEffect(() => setTerm(search), [search])

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault()
    setSearch(term)
    navigate(`/items?q=${encodeURIComponent(term)}`)
    setSidebar(false)
  }

  return (
    <div className="flex min-h-full">
      {/* The drawer backdrop only exists on a narrow screen. */}
      {sidebarOpen ? (
        <button
          aria-label="Close the menu"
          onClick={() => setSidebar(false)}
          className="fixed inset-0 z-30 bg-ink-950/40 lg:hidden"
        />
      ) : null}

      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-ink-200 bg-white',
          'transition-transform dark:border-ink-800 dark:bg-ink-900 lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-14 items-center gap-2 border-b border-ink-200 px-4 dark:border-ink-800">
          <Boxes className="h-5 w-5 text-accent-600" />
          <span className="text-sm font-semibold tracking-tight">HomeStock</span>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {NAV.map((entry) => (
            <NavLink
              key={entry.to}
              to={entry.to}
              end={entry.to === '/'}
              onClick={() => setSidebar(false)}
              className={({ isActive }) =>
                cx(
                  'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-accent-50 font-medium text-accent-700 dark:bg-accent-500/10 dark:text-accent-400'
                    : 'text-ink-600 hover:bg-ink-100 dark:text-ink-300 dark:hover:bg-ink-800',
                )
              }
            >
              {entry.icon}
              {entry.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-ink-200 p-3 dark:border-ink-800">
          <p className="truncate text-xs text-ink-500">{user?.email}</p>
          <button
            onClick={() => {
              signOut()
              navigate('/login')
            }}
            className="mt-2 flex items-center gap-2 text-sm text-ink-600 hover:text-ink-900 dark:text-ink-400 dark:hover:text-ink-100"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-ink-200 bg-ink-50/90 px-4 backdrop-blur dark:border-ink-800 dark:bg-ink-950/90">
          <Button
            variant="ghost"
            className="px-2 lg:hidden"
            aria-label="Open the menu"
            onClick={() => setSidebar(true)}
          >
            <Menu className="h-5 w-5" />
          </Button>

          <form onSubmit={submitSearch} className="relative min-w-0 flex-1 max-w-xl">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <input
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search every item"
              aria-label="Search every item"
              className="field pl-9"
            />
          </form>

          <Button
            variant="ghost"
            className="px-2"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Use the light theme' : 'Use the dark theme'}
          >
            {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>

      <Toaster />
    </div>
  )
}
