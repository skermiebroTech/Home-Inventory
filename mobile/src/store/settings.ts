/** The choices that the owner makes on the settings screen. */

import AsyncStorage from '@react-native-async-storage/async-storage'
import { create } from 'zustand'

const KEY = 'homestock.settings'

export interface Settings {
  /** Send photographs over WiFi only, so a big upload never eats mobile data. */
  photosOnWifiOnly: boolean
  /** Sync when the application comes to the front. */
  syncOnOpen: boolean
  /** Local reminders for a warranty, a service date, or a lent item. */
  reminders: boolean
}

interface SettingsState extends Settings {
  ready: boolean
  restore: () => Promise<void>
  update: (changes: Partial<Settings>) => Promise<void>
}

const DEFAULTS: Settings = {
  photosOnWifiOnly: true,
  syncOnOpen: true,
  reminders: true,
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  ...DEFAULTS,
  ready: false,

  restore: async () => {
    try {
      const stored = await AsyncStorage.getItem(KEY)
      set({ ...DEFAULTS, ...(stored ? JSON.parse(stored) : {}), ready: true })
    } catch {
      set({ ...DEFAULTS, ready: true })
    }
  },

  update: async (changes) => {
    const next = { ...get(), ...changes }
    set(changes)
    await AsyncStorage.setItem(
      KEY,
      JSON.stringify({
        photosOnWifiOnly: next.photosOnWifiOnly,
        syncOnOpen: next.syncOnOpen,
        reminders: next.reminders,
      }),
    )
  },
}))
