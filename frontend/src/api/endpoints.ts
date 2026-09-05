/** One typed function for every route in the contract. */

import { api, download, request } from './client'
import type {
  AiJob,
  AiStatus,
  BackupSchedule,
  BackupStatus,
  BarcodeProduct,
  DashboardSummary,
  HealthStatus,
  Item,
  ItemDetail,
  ItemPhoto,
  ItemQuery,
  ItemWrite,
  Location,
  LocationNode,
  LocationWrite,
  MaintenanceDue,
  MaintenanceLog,
  MaintenanceWrite,
  Message,
  NfcLookup,
  NfcTag,
  Page,
  Receipt,
  ReceiptDetail,
  Tag,
  TokenPair,
  User,
} from './types'

// --- Auth ---

export const auth = {
  register: (body: { email: string; name: string; password: string }) =>
    request<User>('/api/auth/register', { method: 'POST', body, auth: false }),
  login: (body: { email: string; password: string }) =>
    request<TokenPair>('/api/auth/login', { method: 'POST', body, auth: false }),
  me: () => api.get<User>('/api/auth/me'),
}

// --- Items ---

export const items = {
  list: (query: ItemQuery = {}) =>
    api.get<Page<Item>>('/api/items', query as Record<string, unknown>),
  search: (q: string, page = 1, perPage = 50) =>
    api.get<Page<Item>>('/api/items/search', { q, page, per_page: perPage }),
  get: (id: string) => api.get<ItemDetail>(`/api/items/${id}`),
  create: (body: ItemWrite) => api.post<ItemDetail>('/api/items', body),
  update: (id: string, body: Partial<ItemWrite>) =>
    api.put<ItemDetail>(`/api/items/${id}`, body),
  remove: (id: string) => api.delete<Message>(`/api/items/${id}`),
  bulkCreate: (bodies: ItemWrite[]) =>
    api.post<ItemDetail[]>('/api/items/bulk', { items: bodies }),
  uploadPhotos: (id: string, files: File[]) => {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    return api.upload<ItemPhoto[]>(`/api/items/${id}/photos`, form)
  },
  deletePhoto: (id: string, photoId: string) =>
    api.delete<Message>(`/api/items/${id}/photos/${photoId}`),
  lookupBarcode: (code: string) =>
    api.get<BarcodeProduct>(`/api/items/barcode/${encodeURIComponent(code)}`),
  createFromBarcode: (code: string, query: { location_id?: string; quantity?: number } = {}) =>
    api.post<ItemDetail>(
      `/api/items/barcode/${encodeURIComponent(code)}`,
      undefined,
      query,
    ),
  qrUrl: (id: string, size = 512) => `/api/items/${id}/qr?size=${size}`,
}

// --- Locations ---

export const locations = {
  tree: () => api.get<LocationNode[]>('/api/locations'),
  get: (id: string) => api.get<Location>(`/api/locations/${id}`),
  create: (body: LocationWrite) => api.post<Location>('/api/locations', body),
  update: (id: string, body: Partial<LocationWrite>) =>
    api.put<Location>(`/api/locations/${id}`, body),
  remove: (id: string) => api.delete<Message>(`/api/locations/${id}`),
  qrUrl: (id: string, size = 512) => `/api/locations/${id}/qr?size=${size}`,
}

// --- Tags ---

export const tags = {
  list: () => api.get<Tag[]>('/api/tags'),
  create: (body: { name: string; color?: string }) => api.post<Tag>('/api/tags', body),
  update: (id: string, body: { name?: string; color?: string }) =>
    api.put<Tag>(`/api/tags/${id}`, body),
  remove: (id: string) => api.delete<Message>(`/api/tags/${id}`),
  assign: (tagId: string, itemId: string) =>
    api.post<ItemDetail>(`/api/tags/${tagId}/items/${itemId}`),
  unassign: (tagId: string, itemId: string) =>
    api.delete<ItemDetail>(`/api/tags/${tagId}/items/${itemId}`),
}

// --- Lending ---

export const lending = {
  list: () => api.get<Item[]>('/api/items/lent'),
  lend: (id: string, body: { lent_to: string; lent_date?: string; notes?: string }) =>
    api.post<ItemDetail>(`/api/items/${id}/lend`, body),
  returnItem: (id: string) => api.post<ItemDetail>(`/api/items/${id}/return`),
}

// --- Maintenance ---

export const maintenance = {
  upcoming: (days = 30) => api.get<MaintenanceDue[]>('/api/maintenance/upcoming', { days }),
  forItem: (itemId: string) => api.get<MaintenanceLog[]>(`/api/items/${itemId}/maintenance`),
  create: (itemId: string, body: MaintenanceWrite) =>
    api.post<MaintenanceLog>(`/api/items/${itemId}/maintenance`, body),
  update: (id: string, body: Partial<MaintenanceWrite>) =>
    api.put<MaintenanceLog>(`/api/maintenance/${id}`, body),
}

// --- Receipts ---

export const receipts = {
  list: (query: { vendor?: string; page?: number; per_page?: number } = {}) =>
    api.get<Page<Receipt>>('/api/receipts', query),
  get: (id: string) => api.get<ReceiptDetail>(`/api/receipts/${id}`),
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.upload<ReceiptDetail>('/api/receipts/upload', form)
  },
  update: (
    id: string,
    body: {
      vendor?: string | null
      purchase_date?: string | null
      total_amount?: string | null
      currency?: string | null
    },
  ) => api.put<ReceiptDetail>(`/api/receipts/${id}`, body),
  link: (id: string, itemId: string, lineId?: string) =>
    api.post<ReceiptDetail>(
      `/api/receipts/${id}/link/${itemId}`,
      undefined,
      lineId ? { line_id: lineId } : undefined,
    ),
  remove: (id: string) => api.delete<Message>(`/api/receipts/${id}`),
}

// --- NFC ---

export const nfc = {
  register: (body: {
    nfc_uid: string
    item_id?: string
    location_id?: string
    label?: string
  }) => api.post<NfcTag>('/api/nfc/register', body),
  lookup: (uid: string) => api.get<NfcLookup>(`/api/nfc/${encodeURIComponent(uid)}`),
  remove: (uid: string) => api.delete<Message>(`/api/nfc/${encodeURIComponent(uid)}`),
}

// --- AI ---

export const ai = {
  status: () => api.get<AiStatus>('/api/ai/status'),
  job: (id: string) => api.get<AiJob>(`/api/ai/jobs/${id}`),
  recognize: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.upload<AiJob>('/api/ai/recognize', form)
  },
  bulkScan: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.upload<AiJob>('/api/ai/bulk-scan', form)
  },
  parseReceipt: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.upload<AiJob>('/api/ai/receipt-parse', form)
  },
}

// --- Health, dashboard, export, and backup ---

export const system = {
  health: () => request<HealthStatus>('/api/health', { auth: false }),
  dashboard: () => api.get<DashboardSummary>('/api/dashboard'),
  backupStatus: () => api.get<BackupStatus>('/api/backup/status'),
  setSchedule: (body: BackupSchedule) => api.post<BackupStatus>('/api/backup/schedule', body),
  runBackup: () => api.post<Message>('/api/backup/run'),
  restore: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.upload<Message>('/api/backup/restore', form)
  },
}

export const exports = {
  csv: () => download('/api/export/csv', 'homestock-items.csv'),
  full: () => download('/api/export/full', 'homestock-backup.zip'),
  insurance: (query: { include_photos?: boolean; min_value?: number } = {}) =>
    download('/api/export/insurance-report', 'homestock-insurance.pdf', query),
}
