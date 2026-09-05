/**
 * One receipt.
 *
 * The OCR runs after the upload, so the page asks the server again every few
 * seconds until the parsed data arrives.
 */

import { ArrowLeft, Link2, Save, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { mediaUrl } from '@/api/client'
import {
  Button,
  Card,
  ConfirmDialog,
  ErrorNote,
  Field,
  Input,
  Loading,
  Modal,
  PageHeader,
  Select,
  Spinner,
} from '@/components/ui'
import { useItems } from '@/hooks/useItems'
import {
  useDeleteReceipt,
  useLinkReceiptItem,
  useReceipt,
  useUpdateReceipt,
} from '@/hooks/useOperations'
import { formatMoney } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

export default function ReceiptDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [waiting, setWaiting] = useState(true)
  const { data: receipt, isLoading, error } = useReceipt(id, waiting)
  const update = useUpdateReceipt(id)
  const link = useLinkReceiptItem(id)
  const remove = useDeleteReceipt()
  const { data: itemPage } = useItems({ per_page: 200, sort: 'name' })

  const [form, setForm] = useState({ vendor: '', purchase_date: '', total_amount: '' })
  const [linking, setLinking] = useState<string | null>(null)
  const [chosenItem, setChosenItem] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)

  // The reading is done once the server has written the parsed JSON.
  useEffect(() => {
    if (receipt?.ocr_parsed_json) setWaiting(false)
  }, [receipt?.ocr_parsed_json])

  useEffect(() => {
    if (!receipt) return
    setForm({
      vendor: receipt.vendor ?? '',
      purchase_date: receipt.purchase_date ?? '',
      total_amount: receipt.total_amount ?? '',
    })
  }, [receipt?.id, receipt?.vendor, receipt?.purchase_date, receipt?.total_amount])

  if (isLoading) return <Loading />
  if (error) return <ErrorNote error={error} />
  if (!receipt) return null

  const save = async () => {
    try {
      await update.mutateAsync({
        vendor: form.vendor || null,
        purchase_date: form.purchase_date || null,
        total_amount: form.total_amount || null,
      })
      toastOk('The receipt is saved.')
    } catch (failure) {
      toastError(failure)
    }
  }

  return (
    <div>
      <Link
        to="/receipts"
        className="mb-3 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-200"
      >
        <ArrowLeft className="h-4 w-4" /> Receipts
      </Link>

      <PageHeader
        title={receipt.vendor ?? 'Receipt'}
        subtitle={formatMoney(receipt.total_amount)}
        action={
          <Button
            variant="ghost"
            className="px-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40"
            onClick={() => setConfirmDelete(true)}
            aria-label="Delete this receipt"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-2">
          <img
            src={mediaUrl(receipt.file_path)}
            alt="The receipt"
            className="w-full rounded-lg"
          />
        </Card>

        <div className="space-y-4">
          {waiting && !receipt.ocr_parsed_json ? (
            <Card className="flex items-center gap-3 text-sm text-ink-600 dark:text-ink-300">
              <Spinner />
              <div>
                <p className="font-medium">The server is reading the receipt.</p>
                <p className="text-ink-500">
                  Tesseract runs on the CPU, so this takes a moment. The fields
                  fill themselves.
                </p>
              </div>
            </Card>
          ) : null}

          <Card>
            <h2 className="mb-3 text-sm font-semibold">What the server read</h2>
            <div className="space-y-3">
              <Field label="Store">
                <Input
                  value={form.vendor}
                  onChange={(event) => setForm({ ...form, vendor: event.target.value })}
                />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Date">
                  <Input
                    type="date"
                    value={form.purchase_date}
                    onChange={(event) => setForm({ ...form, purchase_date: event.target.value })}
                  />
                </Field>
                <Field label="Total">
                  <Input
                    inputMode="decimal"
                    value={form.total_amount}
                    onChange={(event) => setForm({ ...form, total_amount: event.target.value })}
                  />
                </Field>
              </div>
              <Button onClick={() => void save()} loading={update.isPending} icon={<Save className="h-4 w-4" />}>
                Save the corrections
              </Button>
            </div>
          </Card>

          <Card>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Lines</h2>
              <Button variant="secondary" onClick={() => setLinking('whole')}>
                Link an item
              </Button>
            </div>
            {receipt.lines.length === 0 ? (
              <p className="text-sm text-ink-500">No line was read.</p>
            ) : (
              <ul className="divide-y divide-ink-200 text-sm dark:divide-ink-800">
                {receipt.lines.map((line) => (
                  <li key={line.id} className="flex items-center gap-2 py-2">
                    <span className="min-w-0 flex-1 truncate">{line.line_text}</span>
                    <span className="text-ink-500">{formatMoney(line.line_amount)}</span>
                    {line.item_id ? (
                      <Link
                        to={`/items/${line.item_id}`}
                        className="text-accent-600 hover:underline dark:text-accent-400"
                        aria-label="Open the linked item"
                      >
                        <Link2 className="h-4 w-4" />
                      </Link>
                    ) : (
                      <button
                        onClick={() => setLinking(line.id)}
                        className="text-xs text-accent-600 hover:underline dark:text-accent-400"
                      >
                        Link
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {receipt.ocr_raw_text ? (
            <Card>
              <details>
                <summary className="cursor-pointer text-sm font-semibold">
                  The raw text
                </summary>
                <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-ink-600 dark:text-ink-300">
                  {receipt.ocr_raw_text}
                </pre>
              </details>
            </Card>
          ) : null}
        </div>
      </div>

      <Modal
        open={linking !== null}
        title="Link this receipt to an item"
        onClose={() => setLinking(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setLinking(null)}>
              Cancel
            </Button>
            <Button
              loading={link.isPending}
              disabled={!chosenItem}
              onClick={async () => {
                try {
                  await link.mutateAsync({
                    itemId: chosenItem,
                    lineId: linking && linking !== 'whole' ? linking : undefined,
                  })
                  toastOk('The receipt is linked.')
                  setLinking(null)
                  setChosenItem('')
                } catch (failure) {
                  toastError(failure)
                }
              }}
            >
              Link
            </Button>
          </>
        }
      >
        <Field label="Item">
          <Select value={chosenItem} onChange={(event) => setChosenItem(event.target.value)}>
            <option value="">Choose an item</option>
            {itemPage?.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
        </Field>
      </Modal>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this receipt?"
        message="The image goes away as well. The items stay."
        loading={remove.isPending}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          try {
            await remove.mutateAsync(id)
            toastOk('The receipt is deleted.')
            navigate('/receipts')
          } catch (failure) {
            toastError(failure)
          }
        }}
      />
    </div>
  )
}
