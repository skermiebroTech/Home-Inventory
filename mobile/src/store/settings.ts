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
  /**
   * The vision model that sits on the phone, by id, or null for none.
   *
   * With one here the camera names an item without the server, which the
   * old Xeons in the cupboard take tens of seconds to do.
   */
  localModel: string | null
}

interface SettingsState extends Settings {
  ready: boolean
  restore: () => Promise<void>
  update: (changes: Partial<Settings>) => Promise<void>
  setLocalModel: (id: string | null) => void
}

const DEFAULTS: Settings = {
  photosOnWifiOnly: true,
  syncOnOpen: true,
  reminders: true,
  localModel: null,
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
        localModel: next.localModel,
      }),
    )
  },

  setLocalModel: (id) => {
    void get().update({ localModel: id })
  },
}))
