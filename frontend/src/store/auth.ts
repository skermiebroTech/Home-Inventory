/**
 * The signed in account, and the tokens.
 *
 * The tokens live in localStorage, so a page reload keeps the session. The
 * store hands the tokens to the HTTP client through `connectTokens`, which
 * lets the client renew an expired access token without importing the store.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import { connectTokens } from '@/api/client'
import { auth } from '@/api/endpoints'
import type { User } from '@/api/types'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  ready: boolean
  signIn: (email: string, password: string) => Promise<void>
  register: (email: string, name: string, password: string) => Promise<void>
  signOut: () => void
  loadUser: () => Promise<void>
  setTokens: (access: string, refresh: string) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      ready: false,

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),

      signIn: async (email, password) => {
        const pair = await auth.login({ email, password })
        set({ accessToken: pair.access_token, refreshToken: pair.refresh_token })
        const user = await auth.me()
        set({ user, ready: true })
      },

      register: async (email, name, password) => {
        await auth.register({ email, name, password })
        await get().signIn(email, password)
      },

      signOut: () => set({ accessToken: null, refreshToken: null, user: null, ready: true }),

      loadUser: async () => {
        if (!get().accessToken) {
          set({ ready: true })
          return
        }
        try {
          set({ user: await auth.me(), ready: true })
        } catch {
          set({ accessToken: null, refreshToken: null, user: null, ready: true })
        }
      },
    }),
    {
      name: 'homestock-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    },
  ),
)

connectTokens({
  accessToken: () => useAuthStore.getState().accessToken,
  refreshToken: () => useAuthStore.getState().refreshToken,
  onRefreshed: (access, refresh) => useAuthStore.getState().setTokens(access, refresh),
  onSignedOut: () => useAuthStore.getState().signOut(),
})
