/**
 * The API contract, as TypeScript types.
 *
 * The shapes follow docs/openapi.yaml. Every money value arrives as a string,
 * because the server sends a decimal and JSON has no decimal type. Format it
 * with `formatMoney` from `@/lib/format`, and never with plain arithmetic.
 */

export interface ErrorDetail {
  code: string
  message: string
  details?: Record<string, unknown> | null
}

export interface Envelope<T> {
  data: T | null
  error: ErrorDetail | null
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface Message {
  message: string
}

// --- Accounts ---

export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// --- Tags ---

export interface Tag {
  id: string
  name: string
  color: string
  created_at: string
  updated_at: string
}

// --- Items ---

export type Condition = 'new' | 'good' | 'fair' | 'poor'

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
  condition: Condition | null
  quantity: number
  notes: string | null
  owner: string | null
  /** The number on the sticker, such as "0000042". */
  asset_tag: string
  is_lent: boolean
  lent_to: string | null
  lent_date: string | null
  version: number
  created_at: string
  updated_at: string
  tags: Tag[]
  primary_photo: ItemPhoto | null
}

export interface ItemDetail extends Item {
  photos: ItemPhoto[]
  location_path: string[]
}

export interface ItemWrite {
  name: string
  description?: string | null
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
  purchase_location?: string | null
  warranty_expires?: string | null
  condition?: Condition | null
  quantity?: number
  notes?: string | null
  owner?: string | null
  tag_ids?: string[]
}

export interface ItemQuery {
  q?: string
  owner?: string
  location_id?: string
  include_sublocations?: boolean
  category?: string
  tag_id?: string[]
  is_lent?: boolean
  condition?: Condition
  warranty_expiring_days?: number
  sort?: string
  page?: number
  per_page?: number
}

// --- Locations ---

export type LocationType = 'room' | 'zone' | 'container'

export interface Location {
  id: string
  user_id: string
  parent_id: string | null
  name: string
  type: LocationType
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

export interface LocationWrite {
  name: string
  type?: LocationType
  parent_id?: string | null
  description?: string | null
  sort_order?: number
}

// --- Receipts ---

export interface ReceiptLine {
  id: string
  receipt_id: string
  item_id: string | null
  line_text: string
  line_amount: string | null
  created_at: string
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

export interface ReceiptDetail extends Receipt {
  ocr_raw_text: string | null
  ocr_parsed_json: Record<string, unknown> | null
  lines: ReceiptLine[]
}

// --- Maintenance ---

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

export interface MaintenanceWrite {
  description: string
  date_performed?: string | null
  next_due_date?: string | null
  cost?: string | null
  notes?: string | null
}

// --- NFC and barcodes ---

export interface NfcTag {
  id: string
  nfc_uid: string
  item_id: string | null
  location_id: string | null
  label: string | null
  created_at: string
  updated_at: string
}

export interface NfcLookup {
  nfc_uid: string
  target_type: 'item' | 'location'
  target_id: string
  target_name: string
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

// --- AI ---

export type AiJobStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type AiJobKind = 'recognize' | 'bulk_scan' | 'receipt_parse'

export interface RecognizedItem {
  name: string
  brand: string | null
  model: string | null
  serial_number: string | null
  category: string | null
  subcategory: string | null
  estimated_value_aud: string | null
  condition: Condition | null
  confidence: number | null
  region: number[] | null
}

export interface RecognizeResult {
  items: RecognizedItem[]
  model: string
  duration_ms: number
  image_count: number
  ocr_text: string | null
}

export interface ParsedReceiptLine {
  name: string
  quantity: string | null
  unit_price: string | null
  total: string | null
}

export interface ParsedReceipt {
  store_name: string | null
  date: string | null
  items: ParsedReceiptLine[]
  subtotal: string | null
  tax: string | null
  grand_total: string | null
  currency: string | null
}

export interface AiJob {
  id: string
  kind: AiJobKind
  status: AiJobStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  error: string | null
  recognize_result: RecognizeResult | null
  receipt_result: ParsedReceipt | null
}

export interface AiStatus {
  enabled: boolean
  reachable: boolean
  base_url: string
  vision_model: string
  text_model: string
  models_installed: string[]
  vision_model_installed: boolean
  text_model_installed: boolean
  gpu_available: boolean
  inline_timeout_seconds: number
  message: string | null
}

// --- Health, dashboard, and backup ---

export interface ComponentHealth {
  ok: boolean
  detail: string | null
  latency_ms: number | null
}

export interface DiskUsage {
  path: string
  total_bytes: number
  used_bytes: number
  free_bytes: number
  percent_used: number
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error'
  version: string
  database: ComponentHealth
  ollama: ComponentHealth
  disk: DiskUsage | null
  secret_key_is_default: boolean
  setup_required: boolean
}

export interface LocationCount {
  location_id: string
  location_name: string
  item_count: number
  total_value: string
}

export interface DashboardSummary {
  total_items: number
  total_quantity: number
  total_value: string
  items_by_location: LocationCount[]
  lent_count: number
  maintenance_due_count: number
  warranty_expiring_count: number
  receipt_count: number
}

export interface BackupSchedule {
  enabled: boolean
  cron: string
  retention: number
  rclone_remote: string | null
}

export interface BackupFile {
  filename: string
  size_bytes: number
  created_at: string
}

export interface BackupStatus {
  schedule: BackupSchedule
  last_run_at: string | null
  last_run_ok: boolean | null
  last_run_error: string | null
  next_run_at: string | null
  backups: BackupFile[]
  backup_dir: string
}

// --- Components ---

export interface Component {
  id: string
  user_id: string
  name: string
  brand: string | null
  model_number: string | null
  category: string | null
  description: string | null
  /** What one costs, when the fitted part names no price. */
  default_price: string | null
  is_consumable: boolean
  version: number
  created_at: string
  updated_at: string
  thumbnail_path: string | null
  photo_count: number
}

export interface ComponentUse {
  item_id: string
  item_name: string
  quantity: number
}

export interface ComponentDetail extends Component {
  fitted_count: number
  spare_quantity: number
  fitted_to: ComponentUse[]
}

export interface ComponentWrite {
  name: string
  brand?: string | null
  model_number?: string | null
  category?: string | null
  description?: string | null
  default_price?: string | null
  is_consumable?: boolean
}

export interface ItemComponent {
  id: string
  item_id: string
  component_id: string
  quantity: number
  /** What this one cost. Null means the default price of the catalogue. */
  price: string | null
  serial_number: string | null
  fitted_on: string | null
  notes: string | null
  version: number
  created_at: string
  updated_at: string
  name: string
  brand: string | null
  model_number: string | null
  is_consumable: boolean
  default_price: string | null
  effective_price: string | null
  line_total: string | null
}

export interface ItemComponentWrite {
  component_id: string
  quantity?: number
  price?: string | null
  serial_number?: string | null
  fitted_on?: string | null
  notes?: string | null
}

export interface Spare {
  id: string
  user_id: string
  component_id: string
  location_id: string | null
  quantity: number
  minimum_quantity: number
  unit_price: string | null
  notes: string | null
  version: number
  created_at: string
  updated_at: string
  name: string
  brand: string | null
  model_number: string | null
  is_consumable: boolean
  default_price: string | null
  effective_price: string | null
  stock_value: string | null
  location_name: string | null
  is_low: boolean
}

export interface OwnerPhoto {
  id: string
  user_id: string
  owner_type: 'component' | 'cable'
  owner_id: string
  file_path: string
  thumbnail_path: string | null
  is_primary: boolean
  sort_order: number
  caption: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface ActivityLine {
  id: string
  user_id: string
  entity_type: string
  entity_id: string
  action: string
  summary: string
  detail: string | null
  actor: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface Cable {
  id: string
  user_id: string
  name: string
  kind: string | null
  connector_a: string | null
  connector_b: string | null
  length_cm: number | null
  colour: string | null
  brand: string | null
  specification: string | null
  quantity: number
  price: string | null
  notes: string | null
  location_id: string | null
  item_id: string | null
  version: number
  created_at: string
  updated_at: string
  ends: string | null
  length_label: string | null
  total_value: string | null
  location_name: string | null
  item_name: string | null
  thumbnail_path: string | null
  photo_count: number
}

export interface CableWrite {
  name: string
  kind?: string | null
  connector_a?: string | null
  connector_b?: string | null
  length_cm?: number | null
  colour?: string | null
  brand?: string | null
  specification?: string | null
  quantity?: number
  price?: string | null
  notes?: string | null
  location_id?: string | null
  item_id?: string | null
}

export interface CableQuery {
  q?: string
  kind?: string
  connector?: string
  location_id?: string
  item_id?: string
}

export interface SpareWrite {
  component_id: string
  quantity?: number
  minimum_quantity?: number
  location_id?: string | null
  unit_price?: string | null
  notes?: string | null
}
