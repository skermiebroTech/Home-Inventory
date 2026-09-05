/**
 * The address that a QR label holds.
 *
 * A label says /a/0000042. This page turns the number into the item and
 * steps out of the way, so the address in the bar ends as the item itself.
 */

import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { items } from '@/api/endpoints'
import { EmptyState, ErrorNote, Loading } from '@/components/ui'
import { QrCode } from 'lucide-react'

export default function AssetTag() {
  const { tag } = useParams<{ tag: string }>()
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['item-by-tag', tag],
    queryFn: () => items.byTag(tag as string),
    enabled: Boolean(tag),
    retry: false,
  })

  useEffect(() => {
    if (data) navigate(`/items/${data.id}`, { replace: true })
  }, [data, navigate])

  if (isLoading) return <Loading label={`Looking up ${tag}`} />
  if (error) {
    return (
      <div className="space-y-4">
        <EmptyState
          icon={<QrCode className="h-8 w-8" />}
          title={`No item carries the tag ${tag}`}
          hint="The label may belong to another account, or the item is deleted."
        />
        <ErrorNote error={error} />
      </div>
    )
  }
  return <Loading />
}
