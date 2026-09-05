/** The cables section. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { cables } from '@/api/endpoints'
import type { CableQuery, CableWrite } from '@/api/types'
import { keys } from './keys'

export function useCables(query: CableQuery = {}) {
  return useQuery({
    queryKey: keys.cables(query as Record<string, unknown>),
    queryFn: () => cables.list(query),
    placeholderData: (previous) => previous,
  })
}

export function useCableKinds() {
  return useQuery({ queryKey: keys.cableKinds(), queryFn: () => cables.kinds() })
}

export function useCreateCable() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: CableWrite) => cables.create(body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['cables'] }),
  })
}

export function useUpdateCable() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<CableWrite> }) =>
      cables.update(id, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['cables'] }),
  })
}

export function useDeleteCable() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => cables.remove(id),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['cables'] }),
  })
}
