/**
 * The session.
 *
 * The tokens go into the secure store, which is the keychain on iOS and the
 * keystore on Android. The server address is not a secret, so it lives in
 * async storage beside the other settings.
 */

import AsyncStorage from '@react-native-async-storage/async-storage'
import * as SecureStore from 'expo-secure-store'
import { create } from 'zustand'

import { connectTokens, request } from '@/api/client'
import type { TokenPair, User } from '@/api/types'
import { getMeta, resetDatabase, setMeta } from '@/db'

const ACCESS_KEY = 'homestock.access'
const REFRESH_KEY = 'homestock.refresh'
const SERVER_KEY = 'homestock.server'
/** The account that the rows in SQLite belong to. */
const OWNER_KEY = 'owner'

interface AuthState {
  serverUrl: string
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  ready: boolean
  restore: () => Promise<void>
  signIn: (server: string, email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  setTokens: (access: string, refresh: string) => void
}

/**
 * Give the local cache to the account that signed in.
 *
 * Two accounts on one phone must not mix. When a different person signs in,
 * the items of the last person go, and so do the changes they queued. The
 * cache of an install that never recorded an owner stays, because it belongs
 * to the same person: only the name is new.
 */
async function claimTheCache(userId: string): Promise<void> {
  const owner = await getMeta(OWNER_KEY)
  if (owner === userId) return
  if (owner !== null) await resetDatabase()
  await setMeta(OWNER_KEY, userId)
}

async function save(key: string, value: string | null): Promise<void> {
  if (value === null) await SecureStore.deleteItemAsync(key)
  else await SecureStore.setItemAsync(key, value)
}

export const useAuthStore = create<AuthState>((set, get) => ({
  serverUrl: '',
  accessToken: null,
  refreshToken: null,
  user: null,
  ready: false,

  restore: async () => {
    const [server, access, refresh] = await Promise.all([
      AsyncStorage.getItem(SERVER_KEY),
      SecureStore.getItemAsync(ACCESS_KEY),
      SecureStore.getItemAsync(REFRESH_KEY),
    ])
    set({
      serverUrl: server ?? process.env.EXPO_PUBLIC_DEFAULT_SERVER ?? '',
      accessToken: access,
      refreshToken: refresh,
      ready: true,
    })
    if (access) {
      try {
        const user = await request<User>('/api/auth/me')
        set({ user })
        await setMeta(OWNER_KEY, user.id)
      } catch {
        // The token is old, or the server is away. The cached data still
        // shows, and the next sync tries again.
      }
    }
  },

  signIn: async (server, email, password) => {
    const base = server.replace(/\/$/, '')
    await AsyncStorage.setItem(SERVER_KEY, base)
    set({ serverUrl: base })

    const pair = await request<TokenPair>('/api/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
      baseUrl: base,
    })
    await save(ACCESS_KEY, pair.access_token)
    await save(REFRESH_KEY, pair.refresh_token)
    set({ accessToken: pair.access_token, refreshToken: pair.refresh_token })

    const user = await request<User>('/api/auth/me')
    set({ user })
    await claimTheCache(user.id)
  },

  signOut: async () => {
    await save(ACCESS_KEY, null)
    await save(REFRESH_KEY, null)
    set({ accessToken: null, refreshToken: null, user: null })
  },

  setTokens: (access, refresh) => {
    void save(ACCESS_KEY, access)
    void save(REFRESH_KEY, refresh)
    set({ accessToken: access, refreshToken: refresh })
  },
}))

connectTokens({
  baseUrl: () => useAuthStore.getState().serverUrl,
  accessToken: () => useAuthStore.getState().accessToken,
  refreshToken: () => useAuthStore.getState().refreshToken,
  onRefreshed: (access, refresh) => useAuthStore.getState().setTokens(access, refresh),
  onSignedOut: () => void useAuthStore.getState().signOut(),
})
