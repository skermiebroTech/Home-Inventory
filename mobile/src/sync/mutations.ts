/**
 * Every write that the application makes.
 *
 * A write lands in SQLite at once, so the screen updates with no network, and
 * it joins the outbox for the next sync. The client makes the UUID, so a
 * repeated push never creates a second row.
 */

import * as Crypto from 'expo-crypto'

import type { Item, MaintenanceLog } from '@/api/types'
import {
  getItem,
  openDatabase,
  queueChange,
  queuePhoto,
  upsertItems,
  upsertMaintenance,
} from '@/db'

export function newId(): string {
  return Crypto.randomUUID()
}

function now(): string {
  return new Date().toISOString()
}

export interface ItemDraft {
  name: string
  location_id?: string | null
  category?: string | null
  subcategory?: string | null
  brand?: string | null
  model?: string | null
  serial_number?: string | null
  barcode?: string | null
  purchase_price?: string | null
  current_value?: string | null
  purchase_date?: string | null
  warranty_expires?: string | null
  condition?: string | null
  quantity?: number
  notes?: string | null
  description?: string | null
}

/** Create an item on the phone, and queue it for the server. */
export async function createItem(draft: ItemDraft): Promise<Item> {
  const id = newId()
  const stamp = now()
  const item: Item = {
    id,
    user_id: '',
    location_id: draft.location_id ?? null,
    name: draft.name,
    description: draft.description ?? null,
    category: draft.category ?? null,
    subcategory: draft.subcategory ?? null,
    brand: draft.brand ?? null,
    model: draft.model ?? null,
    serial_number: draft.serial_number ?? null,
    barcode: draft.barcode ?? null,
    purchase_price: draft.purchase_price ?? null,
    current_value: draft.current_value ?? null,
    purchase_date: draft.purchase_date ?? null,
    purchase_location: null,
    warranty_expires: draft.warranty_expires ?? null,
    condition: draft.condition ?? null,
    quantity: draft.quantity ?? 1,
    notes: draft.notes ?? null,
    is_lent: false,
    lent_to: null,
    lent_date: null,
    version: 1,
    created_at: stamp,
    updated_at: stamp,
  }

  await upsertItems([item], 1)
  await queueChange('item', 'create', id, payloadOf(item), null)
  return item
}

/** Change an item on the phone, and queue the change. */
export async function updateItem(
  id: string,
  changes: Partial<ItemDraft> & { is_lent?: boolean; lent_to?: string | null; lent_date?: string | null },
): Promise<void> {
  const current = await getItem(id)
  if (!current) return
  const next = { ...current, ...changes, updated_at: now() } as Item
  await upsertItems([next], 1)
  await queueChange('item', 'update', id, changes as Record<string, unknown>, current.version)
}

export async function deleteItem(id: string): Promise<void> {
  const current = await getItem(id)
  const db = await openDatabase()
  await db.runAsync('DELETE FROM items WHERE id = ?', id)
  await queueChange('item', 'delete', id, null, current?.version ?? null)
}

export async function lendItem(id: string, borrower: string): Promise<void> {
  await updateItem(id, {
    is_lent: true,
    lent_to: borrower,
    lent_date: now().slice(0, 10),
  })
}

export async function returnItem(id: string): Promise<void> {
  await updateItem(id, { is_lent: false, lent_to: null, lent_date: null })
}

export async function addMaintenance(
  itemId: string,
  entry: { description: string; date_performed?: string | null; next_due_date?: string | null; cost?: string | null },
): Promise<void> {
  const id = newId()
  const stamp = now()
  const log: MaintenanceLog = {
    id,
    item_id: itemId,
    description: entry.description,
    date_performed: entry.date_performed ?? stamp.slice(0, 10),
    next_due_date: entry.next_due_date ?? null,
    cost: entry.cost ?? null,
    notes: null,
    version: 1,
    created_at: stamp,
    updated_at: stamp,
  }
  await upsertMaintenance([log])
  await queueChange('maintenance', 'create', id, {
    item_id: itemId,
    description: log.description,
    date_performed: log.date_performed,
    next_due_date: log.next_due_date,
    cost: log.cost,
  }, null)
}

/** Attach a photograph. The file waits in the queue until the sync sends it. */
export async function attachPhoto(itemId: string, localUri: string): Promise<void> {
  await queuePhoto(itemId, localUri)
}

function payloadOf(item: Item): Record<string, unknown> {
  return {
    name: item.name,
    location_id: item.location_id,
    description: item.description,
    category: item.category,
    subcategory: item.subcategory,
    brand: item.brand,
    model: item.model,
    serial_number: item.serial_number,
    barcode: item.barcode,
    purchase_price: item.purchase_price,
    current_value: item.current_value,
    purchase_date: item.purchase_date,
    warranty_expires: item.warranty_expires,
    condition: item.condition,
    quantity: item.quantity,
    notes: item.notes,
  }
}
