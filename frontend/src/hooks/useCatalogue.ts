/** Locations and tags. Both are small lists that many pages read. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { locations, tags } from '@/api/endpoints'
import type { LocationNode, LocationWrite } from '@/api/types'
import { keys } from './keys'

export function useLocationTree() {
  return useQuery({ queryKey: keys.locations(), queryFn: () => locations.tree() })
}

/** Flatten the tree, and give each entry its full path for a dropdown. */
export function flattenTree(
  nodes: LocationNode[],
  depth = 0,
  prefix = '',
): Array<{ id: string; label: string; depth: number; node: LocationNode }> {
  const rows: Array<{ id: string; label: string; depth: number; node: LocationNode }> = []
  for (const node of nodes) {
    const label = prefix ? `${prefix} / ${node.name}` : node.name
    rows.push({ id: node.id, label, depth, node })
    rows.push(...flattenTree(node.children, depth + 1, label))
  }
  return rows
}

export function useCreateLocation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: LocationWrite) => locations.create(body),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.locations() }),
  })
}

export function useUpdateLocation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<LocationWrite> }) =>
      locations.update(id, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.locations() }),
  })
}

export function useDeleteLocation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => locations.remove(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.locations() })
      void client.invalidateQueries({ queryKey: ['items'] })
    },
  })
}

export function useTags() {
  return useQuery({ queryKey: keys.tags(), queryFn: () => tags.list() })
}

export function useCreateTag() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; color?: string }) => tags.create(body),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.tags() }),
  })
}

export function useUpdateTag() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: { name?: string; color?: string } }) =>
      tags.update(id, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.tags() })
      void client.invalidateQueries({ queryKey: ['items'] })
    },
  })
}

export function useDeleteTag() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => tags.remove(id),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.tags() })
      void client.invalidateQueries({ queryKey: ['items'] })
    },
  })
}
