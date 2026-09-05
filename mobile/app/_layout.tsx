/**
 * The root layout.
 *
 * It opens the local database, restores the session, and syncs when the
 * application comes to the front. Every screen below reads SQLite, so the
 * whole interface works with no network.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Stack, useRouter, useSegments } from 'expo-router'
import { StatusBar } from 'expo-status-bar'
import { useEffect, useRef, useState } from 'react'
import { AppState, type AppStateStatus, View } from 'react-native'
import { GestureHandlerRootView } from 'react-native-gesture-handler'
import { SafeAreaProvider } from 'react-native-safe-area-context'

import { Loading } from '@/components/ui'
import { openDatabase } from '@/db'
import { scheduleReminders } from '@/lib/notifications'
import { useAuthStore } from '@/store/auth'
import { useSettingsStore } from '@/store/settings'
import { useSyncStore } from '@/store/sync'
import { useTheme } from '@/theme'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 0, refetchOnWindowFocus: false } },
})

export default function RootLayout() {
  const theme = useTheme()
  const [ready, setReady] = useState(false)
  const restoreAuth = useAuthStore((state) => state.restore)
  const restoreSettings = useSettingsStore((state) => state.restore)

  useEffect(() => {
    void (async () => {
      await openDatabase()
      await Promise.all([restoreAuth(), restoreSettings()])
      await useSyncStore.getState().refreshCounts()
      setReady(true)
    })()
  }, [restoreAuth, restoreSettings])

  if (!ready) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', backgroundColor: theme.bg }}>
        <Loading label="Opening HomeStock" />
      </View>
    )
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar style={theme.dark ? 'light' : 'dark'} />
          <SessionGate />
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.bg } }}>
            <Stack.Screen name="(auth)" />
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="items/[id]" options={{ headerShown: true, title: 'Item' }} />
            <Stack.Screen name="items/add" options={{ headerShown: true, title: 'Add an item' }} />
            <Stack.Screen
              name="receipts/[id]"
              options={{ headerShown: true, title: 'Receipt' }}
            />
          </Stack>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  )
}

/** Send the visitor to the sign in screen, and sync on every foreground. */
function SessionGate() {
  const router = useRouter()
  const segments = useSegments()
  const accessToken = useAuthStore((state) => state.accessToken)
  const syncOnOpen = useSettingsStore((state) => state.syncOnOpen)
  const reminders = useSettingsStore((state) => state.reminders)
  const appState = useRef(AppState.currentState)

  useEffect(() => {
    const inAuth = segments[0] === '(auth)'
    if (!accessToken && !inAuth) router.replace('/(auth)/login')
    if (accessToken && inAuth) router.replace('/(tabs)/home')
  }, [accessToken, segments, router])

  useEffect(() => {
    if (!accessToken || !syncOnOpen) return

    const sync = async (): Promise<void> => {
      await useSyncStore.getState().run()
      if (reminders) await scheduleReminders()
    }
    void sync()

    const listener = AppState.addEventListener('change', (next: AppStateStatus) => {
      if (appState.current.match(/inactive|background/) && next === 'active') void sync()
      appState.current = next
    })
    return () => listener.remove()
  }, [accessToken, syncOnOpen, reminders])

  return null
}
