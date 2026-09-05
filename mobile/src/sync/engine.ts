/**
 * The sync engine.
 *
 * Pull: ask the server for everything that changed since the last sync, and
 * write it into SQLite. Push: send the outbox. The server wins every
 * conflict, and a conflict comes back so the interface can say so.
 *
 * Photographs travel on their own queue, because they are large. The default
 * setting holds them until the phone has WiFi.
 */

import * as Network from 'expo-network'

import { OfflineError, api } from '@/api/client'
import type { SyncChange, SyncChanges, SyncPushResult } from '@/api/types'
import {
  clearOutbox,
  clearPhoto,
  deleteRows,
  getMeta,
  markOutboxError,
  markPhotoError,
  readOutbox,
  readPhotoQueue,
  setMeta,
  upsertItems,
  upsertLocations,
  upsertMaintenance,
  upsertPhotos,
  upsertReceipts,
  upsertTags,
} from '@/db'

const LAST_SYNC = 'last_sync'
/** A change that failed this many times waits for the user, not the engine. */
const MAX_TRIES = 5

export interface SyncSummary {
  pulled: number
  pushed: number
  conflicts: number
  photos: number
  serverTime: string | null
  error: string | null
  /** One message for each change that the server refused. */
  failures: string[]
}

export async function isOnline(): Promise<boolean> {
  try {
    const state = await Network.getNetworkStateAsync()
    return Boolean(state.isConnected && state.isInternetReachable !== false)
  } catch {
    return true
  }
}

export async function onWifi(): Promise<boolean> {
  try {
    const state = await Network.getNetworkStateAsync()
    return state.type === Network.NetworkStateType.WIFI
  } catch {
    return false
  }
}

/** Read the changes since the last sync and write them into SQLite. */
export async function pull(): Promise<{ count: number; serverTime: string }> {
  const since = await getMeta(LAST_SYNC)
  const changes = await api.get<SyncChanges>('/api/sync/changes', {
    since: since ?? undefined,
    limit: 1000,
  })

  await upsertLocations(changes.locations ?? [])
  await upsertTags(changes.tags ?? [])
  await upsertItems(changes.items ?? [])
  await upsertPhotos(changes.item_photos ?? [])
  await upsertReceipts(changes.receipts ?? [])
  await upsertMaintenance(changes.maintenance_logs ?? [])

  // A hard delete never reaches a delta query, so the server sends the ids
  // of the rows that it marked deleted.
  const deleted = changes.deleted ?? {}
  await deleteRows('items', deleted.item ?? [])
  await deleteRows('locations', deleted.location ?? [])
  await deleteRows('receipts', deleted.receipt ?? [])
  await deleteRows('maintenance_logs', deleted.maintenance ?? [])
  await deleteRows('item_photos', deleted.item_photo ?? [])

  const count =
    (changes.items?.length ?? 0) +
    (changes.locations?.length ?? 0) +
    (changes.tags?.length ?? 0) +
    (changes.receipts?.length ?? 0) +
    (changes.maintenance_logs?.length ?? 0) +
    (changes.item_photos?.length ?? 0)

  await setMeta(LAST_SYNC, changes.server_time)
  return { count, serverTime: changes.server_time }
}

/** Send every queued change. Return how many the server took. */
export async function push(): Promise<{
  applied: number
  conflicts: number
  failures: string[]
}> {
  const rows = (await readOutbox()).filter((row) => row.tries < MAX_TRIES)
  if (rows.length === 0) return { applied: 0, conflicts: 0, failures: [] }

  const changes: SyncChange[] = rows.map((row) => ({
    entity: row.entity,
    op: row.op,
    id: row.record_id,
    base_version: row.base_version,
    payload: row.payload ? (JSON.parse(row.payload) as Record<string, unknown>) : null,
    client_updated_at: row.client_updated_at,
  }))

  const result = await api.post<SyncPushResult>('/api/sync/push', { changes })

  // A change that the server could not write stays in the queue, with the
  // reason on it. Clearing it would throw away the work of the person who
  // made it, and that is the one thing an offline application must not do.
  const failed = new Map(
    (result.errors ?? []).map((entry) => [entry.id, entry.message]),
  )

  // A conflict is settled, not failed: the server copy wins, so the queued
  // edit goes away and the next pull brings the server row down.
  await clearOutbox(
    rows.filter((row) => !failed.has(row.record_id)).map((row) => row.id),
  )

  for (const row of rows.filter((entry) => failed.has(entry.record_id))) {
    await markOutboxError(
      row.id,
      failed.get(row.record_id) ?? 'The server refused this change.',
    )
  }

  return {
    applied: result.applied,
    conflicts: result.conflicts.length,
    failures: (result.errors ?? []).map((entry) => entry.message),
  }
}

/** Upload the queued photographs. Return how many went up. */
export async function uploadPhotos(wifiOnly: boolean): Promise<number> {
  const queue = (await readPhotoQueue()).filter((row) => row.tries < MAX_TRIES)
  if (queue.length === 0) return 0
  if (wifiOnly && !(await onWifi())) return 0

  let sent = 0
  for (const row of queue) {
    const form = new FormData()
    form.append('files', {
      uri: row.local_uri,
      name: `photo-${row.id}.jpg`,
      type: 'image/jpeg',
    } as unknown as Blob)
    try {
      await api.upload(`/api/items/${row.item_id}/photos`, form)
      await clearPhoto(row.id)
      sent += 1
    } catch (error) {
      await markPhotoError(row.id, error instanceof Error ? error.message : 'Upload failed.')
    }
  }
  return sent
}

/** Push, then pull, then send the photographs. */
export async function syncNow(options: { wifiOnly: boolean }): Promise<SyncSummary> {
  const summary: SyncSummary = {
    pulled: 0,
    pushed: 0,
    conflicts: 0,
    photos: 0,
    serverTime: null,
    error: null,
    failures: [],
  }

  if (!(await isOnline())) {
    summary.error = 'The phone is offline.'
    return summary
  }

  try {
    // Push first. A local edit then reaches the server before the pull
    // overwrites the row with the older server copy.
    const pushed = await push()
    summary.pushed = pushed.applied
    summary.conflicts = pushed.conflicts
    summary.failures = pushed.failures

    const pulled = await pull()
    summary.pulled = pulled.count
    summary.serverTime = pulled.serverTime

    summary.photos = await uploadPhotos(options.wifiOnly)
  } catch (error) {
    summary.error =
      error instanceof OfflineError
        ? 'The server is not reachable.'
        : error instanceof Error
          ? error.message
          : 'The sync failed.'
  }
  return summary
}

export async function lastSyncAt(): Promise<string | null> {
  return getMeta(LAST_SYNC)
}
