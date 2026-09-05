/** Lending, maintenance, and receipts. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { lending, maintenance, receipts } from '@/api/endpoints'
import type { MaintenanceWrite } from '@/api/types'
import { keys } from './keys'

// --- Lending ---

export function useLentItems() {
  return useQuery({ queryKey: keys.lent(), queryFn: () => lending.list() })
}

export function useLendItem() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string
      body: { lent_to: string; lent_date?: string; notes?: string }
    }) => lending.lend(id, body),
    onSuccess: (_data, variables) => {
      void client.invalidateQueries({ queryKey: keys.item(variables.id) })
      void client.invalidateQueries({ queryKey: ['items'] })
      void client.invalidateQueries({ queryKey: keys.dashboard() })
    },
  })
}

export function useReturnItem() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => lending.returnItem(id),
    onSuccess: (_data, id) => {
      void client.invalidateQueries({ queryKey: keys.item(id) })
      void client.invalidateQueries({ queryKey: ['items'] })
      void client.invalidateQueries({ queryKey: keys.dashboard() })
    },
  })
}

// --- Maintenance ---

export function useUpcomingMaintenance(days = 30) {
  return useQuery({
    queryKey: keys.upcoming(days),
    queryFn: () => maintenance.upcoming(days),
  })
}

export function useItemMaintenance(itemId: string | undefined) {
  return useQuery({
    queryKey: keys.maintenance(itemId ?? ''),
    queryFn: () => maintenance.forItem(itemId as string),
    enabled: Boolean(itemId),
  })
}

export function useAddMaintenance(itemId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: MaintenanceWrite) => maintenance.create(itemId, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.maintenance(itemId) })
      void client.invalidateQueries({ queryKey: ['maintenance', 'upcoming'] })
      void client.invalidateQueries({ queryKey: keys.dashboard() })
    },
  })
}

export function useUpdateMaintenance(itemId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<MaintenanceWrite> }) =>
      maintenance.update(id, body),
    onSuccess: () => {
      if (itemId) void client.invalidateQueries({ queryKey: keys.maintenance(itemId) })
      void client.invalidateQueries({ queryKey: ['maintenance', 'upcoming'] })
    },
  })
}

// --- Receipts ---

export function useReceipts(vendor?: string, page = 1) {
  return useQuery({
    queryKey: keys.receipts(vendor, page),
    queryFn: () => receipts.list({ vendor, page }),
    placeholderData: (previous) => previous,
  })
}

export function useReceipt(id: string | undefined, poll = false) {
  return useQuery({
    queryKey: keys.receipt(id ?? ''),
    queryFn: () => receipts.get(id as string),
    enabled: Boolean(id),
    // The OCR runs after the upload reply. While it runs, the page asks
    // again every three seconds, until the parsed data appears.
    refetchInterval: poll ? 3000 : false,
  })
}

export function useUploadReceipt() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => receipts.upload(file),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['receipts'] }),
  })
}

export function useUpdateReceipt(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      vendor?: string | null
      purchase_date?: string | null
      total_amount?: string | null
      currency?: string | null
    }) => receipts.update(id, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.receipt(id) })
      void client.invalidateQueries({ queryKey: ['receipts'] })
    },
  })
}

export function useLinkReceiptItem(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, lineId }: { itemId: string; lineId?: string }) =>
      receipts.link(id, itemId, lineId),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.receipt(id) }),
  })
}

export function useDeleteReceipt() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => receipts.remove(id),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['receipts'] }),
  })
}
