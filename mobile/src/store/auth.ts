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

const ACCESS_KEY = 'homestock.access'
const REFRESH_KEY = 'homestock.refresh'
const SERVER_KEY = 'homestock.server'

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
        set({ user: await request<User>('/api/auth/me') })
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
    set({ user: await request<User>('/api/auth/me') })
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
