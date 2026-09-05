/** What the sync engine is doing, for the badge in the header. */

import { create } from 'zustand'

import { countPending, countQueuedPhotos } from '@/db'
import { lastSyncAt, syncNow, type SyncSummary } from '@/sync/engine'
import { useSettingsStore } from './settings'

interface SyncState {
  running: boolean
  lastSync: string | null
  pending: number
  queuedPhotos: number
  lastError: string | null
  lastConflicts: number
  /** One message for each change that the server refused. */
  lastFailures: string[]
  refreshCounts: () => Promise<void>
  run: () => Promise<SyncSummary | null>
}

export const useSyncStore = create<SyncState>((set, get) => ({
  running: false,
  lastSync: null,
  pending: 0,
  queuedPhotos: 0,
  lastError: null,
  lastConflicts: 0,
  lastFailures: [],

  refreshCounts: async () => {
    set({
      pending: await countPending(),
      queuedPhotos: await countQueuedPhotos(),
      lastSync: await lastSyncAt(),
    })
  },

  run: async () => {
    if (get().running) return null
    set({ running: true, lastError: null })
    try {
      const summary = await syncNow({
        wifiOnly: useSettingsStore.getState().photosOnWifiOnly,
      })
      set({
        lastError: summary.error,
        lastConflicts: summary.conflicts,
        lastFailures: summary.failures,
        lastSync: summary.serverTime ?? get().lastSync,
      })
      await get().refreshCounts()
      return summary
    } finally {
      set({ running: false })
    }
  },
}))
