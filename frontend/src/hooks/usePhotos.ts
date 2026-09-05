/** The photographs of a component or a cable, and the item thumbnail. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { items, photos } from '@/api/endpoints'
import { keys } from './keys'

type Owner = 'components' | 'cables'

/** The query key of the list that a change must refresh. */
function ownerKey(owner: Owner): string {
  return owner === 'components' ? 'components' : 'cables'
}

export function usePhotos(owner: Owner, ownerId: string | undefined) {
  return useQuery({
    queryKey: keys.photos(owner, ownerId ?? ''),
    queryFn: () => photos.list(owner, ownerId as string),
    enabled: Boolean(ownerId),
  })
}

export function useUploadOwnerPhotos(owner: Owner, ownerId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => photos.upload(owner, ownerId, files),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.photos(owner, ownerId) })
      void client.invalidateQueries({ queryKey: [ownerKey(owner)] })
    },
  })
}

export function useSetPrimaryOwnerPhoto(owner: Owner, ownerId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (photoId: string) => photos.setPrimary(photoId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.photos(owner, ownerId) })
      void client.invalidateQueries({ queryKey: [ownerKey(owner)] })
    },
  })
}

export function useDeleteOwnerPhoto(owner: Owner, ownerId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (photoId: string) => photos.remove(photoId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.photos(owner, ownerId) })
      void client.invalidateQueries({ queryKey: [ownerKey(owner)] })
    },
  })
}

/** Make one photograph the thumbnail of an item. */
export function useSetPrimaryItemPhoto(itemId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (photoId: string) => items.setPrimaryPhoto(itemId, photoId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.item(itemId) })
      void client.invalidateQueries({ queryKey: ['items'] })
    },
  })
}

export function useOwners() {
  return useQuery({ queryKey: keys.owners(), queryFn: () => items.owners() })
}

export function useItemActivity(itemId: string | undefined) {
  return useQuery({
    queryKey: keys.activity(itemId ?? ''),
    queryFn: () => items.activity(itemId as string),
    enabled: Boolean(itemId),
  })
}
