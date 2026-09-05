/** One place for the query keys, so that an invalidation never misses. */

import type { ItemQuery } from '@/api/types'

export const keys = {
  items: (query?: ItemQuery) => ['items', query ?? {}] as const,
  item: (id: string) => ['item', id] as const,
  search: (q: string, page: number) => ['item-search', q, page] as const,
  lent: () => ['items', 'lent'] as const,
  locations: () => ['locations'] as const,
  tags: () => ['tags'] as const,
  receipts: (vendor?: string, page?: number) => ['receipts', vendor ?? '', page ?? 1] as const,
  receipt: (id: string) => ['receipt', id] as const,
  maintenance: (itemId: string) => ['maintenance', itemId] as const,
  upcoming: (days: number) => ['maintenance', 'upcoming', days] as const,
  dashboard: () => ['dashboard'] as const,
  health: () => ['health'] as const,
  aiStatus: () => ['ai-status'] as const,
  aiJob: (id: string) => ['ai-job', id] as const,
  backup: () => ['backup'] as const,
  components: (query?: Record<string, unknown>) =>
    ['components', query ?? {}] as const,
  component: (id: string) => ['components', 'one', id] as const,
  itemComponents: (itemId: string) => ['item-components', itemId] as const,
  spares: (query?: Record<string, unknown>) => ['spares', query ?? {}] as const,
  cables: (query?: Record<string, unknown>) => ['cables', query ?? {}] as const,
  cableKinds: () => ['cables', 'kinds'] as const,
}
