/** The parts of the API contract that the mobile application reads. */

export interface Envelope<T> {
  data: T | null
  error: { code: string; message: string; details?: Record<string, unknown> | null } | null
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface User {
  id: string
  email: string
  name: string
  role: string
  is_active: boolean
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface Tag {
  id: string
  name: string
  color: string
  created_at: string
  updated_at: string
}

export interface ItemPhoto {
  id: string
  item_id: string
  file_path: string
  thumbnail_path: string | null
  is_primary: boolean
  ai_description: string | null
  /** What OCR read on the photograph. Filled shortly after the upload. */
  ocr_text: string | null
  created_at: string
}

export interface Item {
  id: string
  user_id: string
  location_id: string | null
  name: string
  description: string | null
  category: string | null
  subcategory: string | null
  brand: string | null
  model: string | null
  serial_number: string | null
  barcode: string | null
  purchase_price: string | null
  current_value: string | null
  purchase_date: string | null
  purchase_location: string | null
  warranty_expires: string | null
  condition: string | null
  quantity: number
  notes: string | null
  is_lent: boolean
  lent_to: string | null
  lent_date: string | null
  version: number
  created_at: string
  updated_at: string
  tags?: Tag[]
  primary_photo?: ItemPhoto | null
}

export interface ItemDetail extends Item {
  photos: ItemPhoto[]
  location_path: string[]
}

export interface Location {
  id: string
  user_id: string
  parent_id: string | null
  name: string
  type: string
  description: string | null
  photo_path: string | null
  sort_order: number
  version: number
  created_at: string
  updated_at: string
}

export interface LocationNode extends Location {
  children: LocationNode[]
  item_count: number
}

export interface Receipt {
  id: string
  user_id: string
  file_path: string
  thumbnail_path: string | null
  vendor: string | null
  purchase_date: string | null
  total_amount: string | null
  currency: string
  version: number
  created_at: string
  updated_at: string
}

export interface ReceiptLine {
  id: string
  receipt_id: string
  item_id: string | null
  line_text: string
  line_amount: string | null
  created_at: string
}

export interface ReceiptDetail extends Receipt {
  ocr_raw_text: string | null
  ocr_parsed_json: Record<string, unknown> | null
  lines: ReceiptLine[]
}

export interface MaintenanceLog {
  id: string
  item_id: string
  description: string
  date_performed: string | null
  next_due_date: string | null
  cost: string | null
  notes: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface MaintenanceDue extends MaintenanceLog {
  item_name: string
  days_until_due: number
}

export interface BarcodeProduct {
  barcode: string
  name: string | null
  brand: string | null
  category: string | null
  description: string | null
  image_url: string | null
  estimated_value_aud: string | null
  source: string
}

export interface RecognizedItem {
  name: string
  brand: string | null
  model: string | null
  serial_number: string | null
  category: string | null
  subcategory: string | null
  estimated_value_aud: string | null
  condition: string | null
  confidence: number | null
  region: number[] | null
}

export interface AiJob {
  id: string
  kind: 'recognize' | 'bulk_scan' | 'receipt_parse'
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  created_at: string
  started_at: string | null
  finished_at: string | null
  error: string | null
  recognize_result: {
    items: RecognizedItem[]
    model: string
    duration_ms: number
    image_count: number
    ocr_text: string | null
  } | null
  receipt_result: ParsedReceipt | null
}

export interface ParsedReceipt {
  store_name: string | null
  date: string | null
  items: Array<{ name: string; quantity: string | null; unit_price: string | null; total: string | null }>
  subtotal: string | null
  tax: string | null
  grand_total: string | null
  currency: string | null
}

export interface NfcLookup {
  nfc_uid: string
  target_type: 'item' | 'location'
  target_id: string
  target_name: string
}

export interface DashboardSummary {
  total_items: number
  total_quantity: number
  total_value: string
  items_by_location: Array<{
    location_id: string
    location_name: string
    item_count: number
    total_value: string
  }>
  lent_count: number
  maintenance_due_count: number
  warranty_expiring_count: number
  receipt_count: number
}

// --- Sync ---

export type SyncEntity =
  | 'item'
  | 'item_photo'
  | 'location'
  | 'tag'
  | 'receipt'
  | 'maintenance'
  | 'custom_field'

export type SyncOp = 'create' | 'update' | 'delete'

export interface SyncChanges {
  since: string | null
  server_time: string
  items: Item[]
  item_photos: ItemPhoto[]
  locations: Location[]
  tags: Tag[]
  receipts: Receipt[]
  maintenance_logs: MaintenanceLog[]
  custom_fields: Array<Record<string, unknown>>
  deleted: Partial<Record<SyncEntity, string[]>>
  has_more: boolean
}

export interface SyncChange {
  entity: SyncEntity
  op: SyncOp
  id: string
  base_version?: number | null
  payload?: Record<string, unknown> | null
  client_updated_at: string
}

export interface SyncPushResult {
  applied: number
  rejected: number
  conflicts: Array<{ entity: SyncEntity; id: string; reason: string; server_version: number }>
  server_time: string
}
