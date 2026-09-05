import { HandHelping, Undo2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { mediaUrl } from '@/api/client'
import { Button, Card, EmptyState, Loading, PageHeader } from '@/components/ui'
import { useLentItems, useReturnItem } from '@/hooks/useOperations'
import { formatDate } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

export default function Lending() {
  const { data, isLoading } = useLentItems()
  const returnItem = useReturnItem()

  return (
    <div>
      <PageHeader title="Lending" subtitle="Who has what, and since when." />

      {isLoading ? <Loading /> : null}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<HandHelping className="h-8 w-8" />}
          title="Nothing is out on loan"
          hint="Open an item and press Lend to record who took it."
        />
      ) : null}

      <div className="space-y-3">
        {data?.map((item) => (
          <Card key={item.id} className="flex items-center gap-3">
            {item.primary_photo ? (
              <img
                src={mediaUrl(item.primary_photo.thumbnail_path ?? item.primary_photo.file_path)}
                alt=""
                className="h-12 w-12 rounded-lg object-cover"
              />
            ) : (
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-ink-100 dark:bg-ink-800">
                <HandHelping className="h-5 w-5 text-ink-400" />
              </div>
            )}

            <div className="min-w-0 flex-1">
              <Link to={`/items/${item.id}`} className="truncate text-sm font-medium hover:underline">
                {item.name}
              </Link>
              <p className="text-xs text-ink-500">
                {item.lent_to} has it since {formatDate(item.lent_date)}
              </p>
            </div>

            <Button
              variant="secondary"
              icon={<Undo2 className="h-4 w-4" />}
              loading={returnItem.isPending && returnItem.variables === item.id}
              onClick={async () => {
                try {
                  await returnItem.mutateAsync(item.id)
                  toastOk(`${item.name} is back.`)
                } catch (error) {
                  toastError(error)
                }
              }}
            >
              Returned
            </Button>
          </Card>
        ))}
      </div>
    </div>
  )
}
