/** Item queries and mutations. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { items } from '@/api/endpoints'
import type { ItemDetail, ItemQuery, ItemWrite } from '@/api/types'
import { keys } from './keys'

export function useItems(query: ItemQuery) {
  return useQuery({
    queryKey: keys.items(query),
    queryFn: () => items.list(query),
    placeholderData: (previous) => previous,
  })
}

export function useItem(id: string | undefined) {
  return useQuery({
    queryKey: keys.item(id ?? ''),
    queryFn: () => items.get(id as string),
    enabled: Boolean(id),
  })
}

export function useSearch(q: string, page = 1) {
  return useQuery({
    queryKey: keys.search(q, page),
    queryFn: () => items.search(q, page),
    enabled: q.trim().length > 0,
    placeholderData: (previous) => previous,
  })
}

export function useCreateItem() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: ItemWrite) => items.create(body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['items'] })
      void client.invalidateQueries({ queryKey: keys.dashboard() })
      void client.invalidateQueries({ queryKey: keys.locations() })
    },
  })
}

export function useBulkCreateItems() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (bodies: ItemWrite[]) => items.bulkCreate(bodies),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['items'] })
      void client.invalidateQueries({ queryKey: keys.dashboard() })
    },
  })
}

export function useUpdateItem(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<ItemWrite>) => items.update(id, body),
    // The detail page shows the change at once. A failure puts the old row
    // back, so the interface never shows an edit that the server refused.
    onMutate: async (body) => {
      await client.cancelQueries({ queryKey: keys.item(id) })
      const previous = client.getQueryData<ItemDetail>(keys.item(id))
      if (previous) {
        client.setQueryData<ItemDetail>(keys.item(id), { ...previous, ...body } as ItemDetail)
      }
      return { previous }
    },
    onError: (_error, _body, context) => {
      if (context?.previous) client.setQueryData(keys.item(id), context.previous)
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.item(id) })
      void client.invalidateQueries({ queryKey: ['items'] })
      void client.invalidateQueries({ queryKey: keys.dashboard() })
    },
  })
}

export function useDeleteItem() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => items.remove(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['items'] })
      void client.invalidateQueries({ queryKey: keys.dashboard() })
    },
  })
}

export function useUploadPhotos(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => items.uploadPhotos(id, files),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.item(id) })
      void client.invalidateQueries({ queryKey: ['items'] })
    },
  })
}

export function useDeletePhoto(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (photoId: string) => items.deletePhoto(id, photoId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.item(id) })
      void client.invalidateQueries({ queryKey: ['items'] })
    },
  })
}

export function useBarcodeLookup() {
  return useMutation({ mutationFn: (code: string) => items.lookupBarcode(code) })
}
