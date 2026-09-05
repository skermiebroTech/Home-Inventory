/**
 * The local database.
 *
 * Every read in the application comes from here, so the whole interface works
 * with no network. A write goes into the table and into the outbox, and the
 * sync engine sends the outbox to the server when a connection returns.
 */

import * as SQLite from 'expo-sqlite'

import type { Item, ItemPhoto, Location, MaintenanceLog, Receipt, SyncEntity, SyncOp, Tag } from '@/api/types'

const DATABASE_NAME = 'homestock.db'

let database: SQLite.SQLiteDatabase | null = null

const SCHEMA = `
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  location_id TEXT,
  name TEXT NOT NULL,
  description TEXT,
  category TEXT,
  subcategory TEXT,
  brand TEXT,
  model TEXT,
  serial_number TEXT,
  barcode TEXT,
  purchase_price TEXT,
  current_value TEXT,
  purchase_date TEXT,
  purchase_location TEXT,
  warranty_expires TEXT,
  condition TEXT,
  quantity INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  is_lent INTEGER NOT NULL DEFAULT 0,
  lent_to TEXT,
  lent_date TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT,
  updated_at TEXT,
  pending INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_items_location ON items(location_id);
CREATE INDEX IF NOT EXISTS ix_items_name ON items(name);

CREATE TABLE IF NOT EXISTS item_photos (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  thumbnail_path TEXT,
  is_primary INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_photos_item ON item_photos(item_id);

CREATE TABLE IF NOT EXISTS locations (
  id TEXT PRIMARY KEY,
  parent_id TEXT,
  name TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'room',
  description TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT,
  pending INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tags (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#64748b',
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS item_tags (
  item_id TEXT NOT NULL,
  tag_id TEXT NOT NULL,
  PRIMARY KEY (item_id, tag_id)
);

CREATE TABLE IF NOT EXISTS receipts (
  id TEXT PRIMARY KEY,
  file_path TEXT,
  thumbnail_path TEXT,
  vendor TEXT,
  purchase_date TEXT,
  total_amount TEXT,
  currency TEXT NOT NULL DEFAULT 'AUD',
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT,
  pending INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS maintenance_logs (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  description TEXT NOT NULL,
  date_performed TEXT,
  next_due_date TEXT,
  cost TEXT,
  notes TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT,
  pending INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_logs_item ON maintenance_logs(item_id);

-- Every change made while offline waits here.
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity TEXT NOT NULL,
  op TEXT NOT NULL,
  record_id TEXT NOT NULL,
  payload TEXT,
  base_version INTEGER,
  client_updated_at TEXT NOT NULL,
  tries INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);

-- A photograph waits here until the phone has WiFi.
CREATE TABLE IF NOT EXISTS photo_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id TEXT NOT NULL,
  local_uri TEXT NOT NULL,
  created_at TEXT NOT NULL,
  tries INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
`

export async function openDatabase(): Promise<SQLite.SQLiteDatabase> {
  if (database) return database
  database = await SQLite.openDatabaseAsync(DATABASE_NAME)
  await database.execAsync(SCHEMA)
  return database
}

export async function resetDatabase(): Promise<void> {
  const db = await openDatabase()
  await db.execAsync(`
    DELETE FROM items; DELETE FROM item_photos; DELETE FROM locations;
    DELETE FROM tags; DELETE FROM item_tags; DELETE FROM receipts;
    DELETE FROM maintenance_logs; DELETE FROM outbox; DELETE FROM photo_queue;
    DELETE FROM meta;
  `)
}

// --- Small key and value store ---

export async function getMeta(key: string): Promise<string | null> {
  const db = await openDatabase()
  const row = await db.getFirstAsync<{ value: string }>(
    'SELECT value FROM meta WHERE key = ?',
    key,
  )
  return row?.value ?? null
}

export async function setMeta(key: string, value: string): Promise<void> {
  const db = await openDatabase()
  await db.runAsync(
    'INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?',
    key,
    value,
    value,
  )
}

// --- Rows in, rows out ---

const ITEM_COLUMNS = [
  'id', 'location_id', 'name', 'description', 'category', 'subcategory', 'brand',
  'model', 'serial_number', 'barcode', 'purchase_price', 'current_value',
  'purchase_date', 'purchase_location', 'warranty_expires', 'condition',
  'quantity', 'notes', 'is_lent', 'lent_to', 'lent_date', 'version',
  'created_at', 'updated_at',
] as const

export interface LocalItem extends Item {
  pending: number
}

export async function upsertItems(items: Item[], pending = 0): Promise<void> {
  if (items.length === 0) return
  const db = await openDatabase()
  const placeholders = ITEM_COLUMNS.map(() => '?').join(', ')
  const statement = await db.prepareAsync(
    `INSERT OR REPLACE INTO items (${ITEM_COLUMNS.join(', ')}, pending)
     VALUES (${placeholders}, ?)`,
  )
  try {
    for (const item of items) {
      await statement.executeAsync([
        item.id, item.location_id, item.name, item.description, item.category,
        item.subcategory, item.brand, item.model, item.serial_number, item.barcode,
        item.purchase_price, item.current_value, item.purchase_date,
        item.purchase_location, item.warranty_expires, item.condition,
        item.quantity, item.notes, item.is_lent ? 1 : 0, item.lent_to,
        item.lent_date, item.version, item.created_at, item.updated_at, pending,
      ])
      if (item.tags) {
        await db.runAsync('DELETE FROM item_tags WHERE item_id = ?', item.id)
        for (const tag of item.tags) {
          await db.runAsync(
            'INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)',
            item.id,
            tag.id,
          )
        }
      }
    }
  } finally {
    await statement.finalizeAsync()
  }
}

export async function deleteRows(table: string, ids: string[]): Promise<void> {
  if (ids.length === 0) return
  const db = await openDatabase()
  const marks = ids.map(() => '?').join(', ')
  await db.runAsync(`DELETE FROM ${table} WHERE id IN (${marks})`, ...ids)
}

export async function listItems(options: {
  search?: string
  locationId?: string
  limit?: number
  offset?: number
} = {}): Promise<LocalItem[]> {
  const db = await openDatabase()
  const where: string[] = []
  const args: SQLite.SQLiteBindValue[] = []

  if (options.search?.trim()) {
    const like = `%${options.search.trim()}%`
    where.push('(name LIKE ? OR brand LIKE ? OR category LIKE ? OR serial_number LIKE ?)')
    args.push(like, like, like, like)
  }
  if (options.locationId) {
    where.push('location_id = ?')
    args.push(options.locationId)
  }

  const clause = where.length > 0 ? `WHERE ${where.join(' AND ')}` : ''
  args.push(options.limit ?? 100, options.offset ?? 0)
  const rows = await db.getAllAsync<Record<string, unknown>>(
    `SELECT * FROM items ${clause} ORDER BY name COLLATE NOCASE LIMIT ? OFFSET ?`,
    ...args,
  )
  return rows.map(toItem)
}

export async function getItem(id: string): Promise<LocalItem | null> {
  const db = await openDatabase()
  const row = await db.getFirstAsync<Record<string, unknown>>(
    'SELECT * FROM items WHERE id = ?',
    id,
  )
  return row ? toItem(row) : null
}

export async function getItemPhotos(itemId: string): Promise<ItemPhoto[]> {
  const db = await openDatabase()
  return db.getAllAsync<ItemPhoto>(
    'SELECT * FROM item_photos WHERE item_id = ? ORDER BY is_primary DESC, created_at',
    itemId,
  )
}

function toItem(row: Record<string, unknown>): LocalItem {
  return {
    ...(row as unknown as Item),
    is_lent: Boolean(row.is_lent),
    quantity: Number(row.quantity ?? 1),
    version: Number(row.version ?? 1),
    pending: Number(row.pending ?? 0),
  }
}

export async function upsertLocations(rows: Location[]): Promise<void> {
  const db = await openDatabase()
  for (const row of rows) {
    await db.runAsync(
      `INSERT OR REPLACE INTO locations
       (id, parent_id, name, type, description, sort_order, version, updated_at, pending)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)`,
      row.id, row.parent_id, row.name, row.type, row.description,
      row.sort_order, row.version, row.updated_at,
    )
  }
}

export async function listLocations(): Promise<Location[]> {
  const db = await openDatabase()
  return db.getAllAsync<Location>('SELECT * FROM locations ORDER BY sort_order, name')
}

export async function upsertTags(rows: Tag[]): Promise<void> {
  const db = await openDatabase()
  for (const row of rows) {
    await db.runAsync(
      'INSERT OR REPLACE INTO tags (id, name, color, updated_at) VALUES (?, ?, ?, ?)',
      row.id, row.name, row.color, row.updated_at,
    )
  }
}

export async function listTags(): Promise<Tag[]> {
  const db = await openDatabase()
  return db.getAllAsync<Tag>('SELECT * FROM tags ORDER BY name COLLATE NOCASE')
}

export async function upsertPhotos(rows: ItemPhoto[]): Promise<void> {
  const db = await openDatabase()
  for (const row of rows) {
    await db.runAsync(
      `INSERT OR REPLACE INTO item_photos
       (id, item_id, file_path, thumbnail_path, is_primary, created_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
      row.id, row.item_id, row.file_path, row.thumbnail_path,
      row.is_primary ? 1 : 0, row.created_at,
    )
  }
}

export async function upsertReceipts(rows: Receipt[]): Promise<void> {
  const db = await openDatabase()
  for (const row of rows) {
    await db.runAsync(
      `INSERT OR REPLACE INTO receipts
       (id, file_path, thumbnail_path, vendor, purchase_date, total_amount,
        currency, version, updated_at, pending)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)`,
      row.id, row.file_path, row.thumbnail_path, row.vendor, row.purchase_date,
      row.total_amount, row.currency, row.version, row.updated_at,
    )
  }
}

export async function listReceipts(): Promise<Receipt[]> {
  const db = await openDatabase()
  return db.getAllAsync<Receipt>('SELECT * FROM receipts ORDER BY purchase_date DESC')
}

export async function upsertMaintenance(rows: MaintenanceLog[]): Promise<void> {
  const db = await openDatabase()
  for (const row of rows) {
    await db.runAsync(
      `INSERT OR REPLACE INTO maintenance_logs
       (id, item_id, description, date_performed, next_due_date, cost, notes,
        version, updated_at, pending)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)`,
      row.id, row.item_id, row.description, row.date_performed, row.next_due_date,
      row.cost, row.notes, row.version, row.updated_at,
    )
  }
}

export async function listMaintenance(itemId?: string): Promise<MaintenanceLog[]> {
  const db = await openDatabase()
  if (itemId) {
    return db.getAllAsync<MaintenanceLog>(
      'SELECT * FROM maintenance_logs WHERE item_id = ? ORDER BY date_performed DESC',
      itemId,
    )
  }
  return db.getAllAsync<MaintenanceLog>(
    'SELECT * FROM maintenance_logs WHERE next_due_date IS NOT NULL ORDER BY next_due_date',
  )
}

// --- The outbox ---

export interface OutboxRow {
  id: number
  entity: SyncEntity
  op: SyncOp
  record_id: string
  payload: string | null
  base_version: number | null
  client_updated_at: string
  tries: number
  last_error: string | null
}

export async function queueChange(
  entity: SyncEntity,
  op: SyncOp,
  recordId: string,
  payload: Record<string, unknown> | null,
  baseVersion: number | null,
): Promise<void> {
  const db = await openDatabase()
  await db.runAsync(
    `INSERT INTO outbox (entity, op, record_id, payload, base_version, client_updated_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
    entity,
    op,
    recordId,
    payload ? JSON.stringify(payload) : null,
    baseVersion,
    new Date().toISOString(),
  )
}

export async function readOutbox(limit = 200): Promise<OutboxRow[]> {
  const db = await openDatabase()
  return db.getAllAsync<OutboxRow>('SELECT * FROM outbox ORDER BY id LIMIT ?', limit)
}

export async function clearOutbox(ids: number[]): Promise<void> {
  if (ids.length === 0) return
  const db = await openDatabase()
  const marks = ids.map(() => '?').join(', ')
  await db.runAsync(`DELETE FROM outbox WHERE id IN (${marks})`, ...ids)
}

export async function markOutboxError(id: number, message: string): Promise<void> {
  const db = await openDatabase()
  await db.runAsync(
    'UPDATE outbox SET tries = tries + 1, last_error = ? WHERE id = ?',
    message,
    id,
  )
}

export async function countPending(): Promise<number> {
  const db = await openDatabase()
  const row = await db.getFirstAsync<{ total: number }>('SELECT COUNT(*) AS total FROM outbox')
  return Number(row?.total ?? 0)
}

// --- The photograph queue ---

export interface PhotoQueueRow {
  id: number
  item_id: string
  local_uri: string
  created_at: string
  tries: number
}

export async function queuePhoto(itemId: string, localUri: string): Promise<void> {
  const db = await openDatabase()
  await db.runAsync(
    'INSERT INTO photo_queue (item_id, local_uri, created_at) VALUES (?, ?, ?)',
    itemId,
    localUri,
    new Date().toISOString(),
  )
}

export async function readPhotoQueue(limit = 20): Promise<PhotoQueueRow[]> {
  const db = await openDatabase()
  return db.getAllAsync<PhotoQueueRow>('SELECT * FROM photo_queue ORDER BY id LIMIT ?', limit)
}

export async function clearPhoto(id: number): Promise<void> {
  const db = await openDatabase()
  await db.runAsync('DELETE FROM photo_queue WHERE id = ?', id)
}

export async function markPhotoError(id: number, message: string): Promise<void> {
  const db = await openDatabase()
  await db.runAsync(
    'UPDATE photo_queue SET tries = tries + 1, last_error = ? WHERE id = ?',
    message,
    id,
  )
}

export async function countQueuedPhotos(): Promise<number> {
  const db = await openDatabase()
  const row = await db.getFirstAsync<{ total: number }>('SELECT COUNT(*) AS total FROM photo_queue')
  return Number(row?.total ?? 0)
}
