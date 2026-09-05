import { Receipt as ReceiptIcon, Upload } from 'lucide-react'
import { useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { mediaUrl } from '@/api/client'
import { Button, EmptyState, Loading, PageHeader } from '@/components/ui'
import { useReceipts, useUploadReceipt } from '@/hooks/useOperations'
import { formatDate, formatMoney } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

export default function Receipts() {
  const navigate = useNavigate()
  const { data, isLoading } = useReceipts()
  const upload = useUploadReceipt()
  const input = useRef<HTMLInputElement>(null)

  const send = async (file: File | undefined) => {
    if (!file) return
    try {
      const receipt = await upload.mutateAsync(file)
      toastOk('The receipt is stored. The text reading runs now.')
      navigate(`/receipts/${receipt.id}`)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div>
      <PageHeader
        title="Receipts"
        subtitle="Photograph a receipt. The server reads it and fills the fields."
        action={
          <>
            <input
              ref={input}
              type="file"
              accept="image/*"
              hidden
              onChange={(event) => {
                void send(event.target.files?.[0])
                event.target.value = ''
              }}
            />
            <Button
              onClick={() => input.current?.click()}
              loading={upload.isPending}
              icon={<Upload className="h-4 w-4" />}
            >
              Upload a receipt
            </Button>
          </>
        }
      />

      {isLoading ? <Loading /> : null}

      {data && data.items.length === 0 ? (
        <EmptyState
          icon={<ReceiptIcon className="h-8 w-8" />}
          title="No receipt yet"
          hint="A receipt records what you paid, and it links to the items you bought."
        />
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data?.items.map((receipt) => (
          <Link key={receipt.id} to={`/receipts/${receipt.id}`} className="card overflow-hidden transition-shadow hover:shadow-md">
            {receipt.thumbnail_path ? (
              <img
                src={mediaUrl(receipt.thumbnail_path)}
                alt=""
                loading="lazy"
                className="h-32 w-full object-cover"
              />
            ) : (
              <div className="flex h-32 items-center justify-center bg-ink-100 dark:bg-ink-800">
                <ReceiptIcon className="h-7 w-7 text-ink-400" />
              </div>
            )}
            <div className="p-3">
              <p className="truncate text-sm font-medium">{receipt.vendor ?? 'Not read yet'}</p>
              <p className="text-xs text-ink-500">
                {formatDate(receipt.purchase_date)} · {formatMoney(receipt.total_amount)}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
