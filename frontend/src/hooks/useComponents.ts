/** The component catalogue, the fitted parts, and the spares. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { components, spares } from '@/api/endpoints'
import type {
  ComponentWrite,
  ItemComponentWrite,
  SpareWrite,
} from '@/api/types'
import { keys } from './keys'

// --- The catalogue ---

export function useComponents(query: { q?: string; consumable?: boolean } = {}) {
  return useQuery({
    queryKey: keys.components(query),
    queryFn: () => components.list(query),
    placeholderData: (previous) => previous,
  })
}

export function useComponent(id: string | undefined) {
  return useQuery({
    queryKey: keys.component(id ?? ''),
    queryFn: () => components.get(id as string),
    enabled: Boolean(id),
  })
}

export function useCreateComponent() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: ComponentWrite) => components.create(body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['components'] }),
  })
}

export function useUpdateComponent() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<ComponentWrite> }) =>
      components.update(id, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['components'] })
      void client.invalidateQueries({ queryKey: ['spares'] })
      void client.invalidateQueries({ queryKey: ['item-components'] })
    },
  })
}

export function useDeleteComponent() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => components.remove(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['components'] })
      void client.invalidateQueries({ queryKey: ['spares'] })
    },
  })
}

// --- Fitted to an item ---

export function useItemComponents(itemId: string | undefined) {
  return useQuery({
    queryKey: keys.itemComponents(itemId ?? ''),
    queryFn: () => components.forItem(itemId as string),
    enabled: Boolean(itemId),
  })
}

export function useFitComponent(itemId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: ItemComponentWrite) => components.fit(itemId, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.itemComponents(itemId) })
      void client.invalidateQueries({ queryKey: ['components'] })
    },
  })
}

export function useUpdateFitted(itemId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string
      body: Partial<Omit<ItemComponentWrite, 'component_id'>>
    }) => components.updateFitted(id, body),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: keys.itemComponents(itemId) }),
  })
}

export function useRemoveFitted(itemId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => components.removeFitted(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.itemComponents(itemId) })
      void client.invalidateQueries({ queryKey: ['components'] })
    },
  })
}

// --- Spares ---

export function useSpares(query: { low_only?: boolean; consumable?: boolean } = {}) {
  return useQuery({
    queryKey: keys.spares(query),
    queryFn: () => spares.list(query),
    placeholderData: (previous) => previous,
  })
}

export function useCreateSpare() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: SpareWrite) => spares.create(body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['spares'] }),
  })
}

export function useUpdateSpare() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string
      body: Partial<Omit<SpareWrite, 'component_id'>>
    }) => spares.update(id, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['spares'] }),
  })
}

export function useUseSpare() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, count, note }: { id: string; count?: number; note?: string }) =>
      spares.use(id, count ?? 1, note),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['spares'] }),
  })
}

export function useDeleteSpare() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => spares.remove(id),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['spares'] }),
  })
}
