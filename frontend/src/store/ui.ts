/** Client state that no server holds: the theme and the header search text. */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Theme = 'light' | 'dark'

interface UiState {
  theme: Theme
  sidebarOpen: boolean
  search: string
  toggleTheme: () => void
  setTheme: (theme: Theme) => void
  setSidebar: (open: boolean) => void
  setSearch: (text: string) => void
}

function apply(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

function preferred(): Theme {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      theme: preferred(),
      sidebarOpen: false,
      search: '',
      toggleTheme: () => {
        const next: Theme = get().theme === 'dark' ? 'light' : 'dark'
        apply(next)
        set({ theme: next })
      },
      setTheme: (theme) => {
        apply(theme)
        set({ theme })
      },
      setSidebar: (open) => set({ sidebarOpen: open }),
      setSearch: (text) => set({ search: text }),
    }),
    {
      name: 'homestock-theme',
      partialize: (state) => ({ theme: state.theme }),
      onRehydrateStorage: () => (state) => {
        if (state) apply(state.theme)
      },
    },
  ),
)
