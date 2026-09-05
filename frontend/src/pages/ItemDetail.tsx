/** One item: everything about it, and every action on it. */

import {
  ArrowLeft,
  HandHelping,
  MapPin,
  Pencil,
  QrCode,
  Trash2,
  Undo2,
  Wrench,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import ItemForm, { itemToValues, type ItemFormValues } from '@/components/ItemForm'
import PhotoUploader from '@/components/PhotoUploader'
import QrImage from '@/components/QrImage'
import { TagList } from '@/components/pickers'
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  ErrorNote,
  Field,
  Input,
  Loading,
  Modal,
  PageHeader,
  Textarea,
} from '@/components/ui'
import { useDeleteItem, useItem, useUpdateItem } from '@/hooks/useItems'
import {
  useAddMaintenance,
  useItemMaintenance,
  useLendItem,
  useReturnItem,
} from '@/hooks/useOperations'
import { formatDate, formatMoney, today } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-ink-500">{label}</dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
    </div>
  )
}

export default function ItemDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { data: item, isLoading, error } = useItem(id)
  const update = useUpdateItem(id)
  const remove = useDeleteItem()
  const lend = useLendItem()
  const returnItem = useReturnItem()
  const logs = useItemMaintenance(id)
  const addLog = useAddMaintenance(id)

  const [editing, setEditing] = useState(false)
  const [values, setValues] = useState<ItemFormValues | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [lendOpen, setLendOpen] = useState(false)
  const [borrower, setBorrower] = useState('')
  const [logOpen, setLogOpen] = useState(false)
  const [logForm, setLogForm] = useState({ description: '', next_due_date: '', cost: '' })
  const [qrOpen, setQrOpen] = useState(false)

  if (isLoading) return <Loading />
  if (error) return <ErrorNote error={error} />
  if (!item) return null

  const startEdit = () => {
    setValues(itemToValues(item))
    setEditing(true)
  }

  const save = async () => {
    if (!values) return
    try {
      await update.mutateAsync(values)
      toastOk('The item is saved.')
      setEditing(false)
    } catch (failure) {
      toastError(failure)
    }
  }

  return (
    <div>
      <Link
        to="/items"
        className="mb-3 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-200"
      >
        <ArrowLeft className="h-4 w-4" /> Items
      </Link>

      <PageHeader
        title={item.name}
        subtitle={item.location_path.join(' / ') || 'No location'}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setQrOpen(true)} icon={<QrCode className="h-4 w-4" />}>
              Label
            </Button>
            {item.is_lent ? (
              <Button
                variant="secondary"
                loading={returnItem.isPending}
                icon={<Undo2 className="h-4 w-4" />}
                onClick={async () => {
                  try {
                    await returnItem.mutateAsync(id)
                    toastOk('The item is back.')
                  } catch (failure) {
                    toastError(failure)
                  }
                }}
              >
                Mark returned
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={() => setLendOpen(true)}
                icon={<HandHelping className="h-4 w-4" />}
              >
                Lend
              </Button>
            )}
            <Button onClick={startEdit} icon={<Pencil className="h-4 w-4" />}>
              Edit
            </Button>
            <Button
              variant="ghost"
              onClick={() => setConfirmDelete(true)}
              aria-label="Delete this item"
              className="px-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        }
      />

      {item.is_lent ? (
        <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          {item.lent_to} has this since {formatDate(item.lent_date)}.
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <h2 className="mb-3 text-sm font-semibold">Photographs</h2>
            <PhotoUploader itemId={item.id} photos={item.photos} />
          </Card>

          <Card>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <Wrench className="h-4 w-4 text-ink-400" /> Service history
              </h2>
              <Button variant="secondary" onClick={() => setLogOpen(true)}>
                Record work
              </Button>
            </div>
            {(logs.data?.length ?? 0) === 0 ? (
              <p className="text-sm text-ink-500">No work recorded.</p>
            ) : (
              <ul className="space-y-2">
                {logs.data?.map((log) => (
                  <li
                    key={log.id}
                    className="rounded-lg border border-ink-200 p-3 text-sm dark:border-ink-800"
                  >
                    <p className="font-medium">{log.description}</p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      Done {formatDate(log.date_performed)}
                      {log.next_due_date ? ` · next ${formatDate(log.next_due_date)}` : ''}
                      {log.cost ? ` · ${formatMoney(log.cost)}` : ''}
                    </p>
                    {log.notes ? <p className="mt-1 text-ink-600 dark:text-ink-300">{log.notes}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <Card>
          <h2 className="mb-3 text-sm font-semibold">Details</h2>
          <dl className="space-y-3">
            <Detail label="Value" value={formatMoney(item.current_value ?? item.purchase_price)} />
            <Detail label="Quantity" value={item.quantity} />
            <Detail label="Category" value={[item.category, item.subcategory].filter(Boolean).join(' / ')} />
            <Detail label="Brand and model" value={[item.brand, item.model].filter(Boolean).join(' ')} />
            <Detail label="Serial number" value={item.serial_number} />
            <Detail label="Barcode" value={item.barcode} />
            <Detail label="Condition" value={item.condition} />
            <Detail label="Bought" value={formatDate(item.purchase_date)} />
            <Detail label="Bought at" value={item.purchase_location} />
            <Detail label="Paid" value={item.purchase_price ? formatMoney(item.purchase_price) : null} />
            <Detail label="Warranty ends" value={formatDate(item.warranty_expires)} />
            <Detail
              label="Location"
              value={
                item.location_path.length > 0 ? (
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5 text-ink-400" />
                    {item.location_path.join(' / ')}
                  </span>
                ) : null
              }
            />
            <Detail label="Description" value={item.description} />
            <Detail label="Notes" value={<span className="whitespace-pre-line">{item.notes}</span>} />
            <Detail label="Tags" value={item.tags.length ? <TagList tags={item.tags} /> : null} />
            <Detail label="Version" value={<Badge>v{item.version}</Badge>} />
          </dl>
        </Card>
      </div>

      <Modal open={editing} wide title="Edit the item" onClose={() => setEditing(false)}>
        {values ? (
          <ItemForm
            values={values}
            onChange={setValues}
            onSubmit={() => void save()}
            onCancel={() => setEditing(false)}
            saving={update.isPending}
          />
        ) : null}
      </Modal>

      <Modal
        open={lendOpen}
        title="Lend this item"
        onClose={() => setLendOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setLendOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={lend.isPending}
              onClick={async () => {
                try {
                  await lend.mutateAsync({
                    id,
                    body: { lent_to: borrower, lent_date: today() },
                  })
                  toastOk(`${borrower} has the item.`)
                  setLendOpen(false)
                  setBorrower('')
                } catch (failure) {
                  toastError(failure)
                }
              }}
            >
              Lend
            </Button>
          </>
        }
      >
        <Field label="Who has it">
          <Input
            autoFocus
            value={borrower}
            onChange={(event) => setBorrower(event.target.value)}
            placeholder="Dave next door"
          />
        </Field>
      </Modal>

      <Modal
        open={logOpen}
        title="Record service work"
        onClose={() => setLogOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setLogOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={addLog.isPending}
              onClick={async () => {
                try {
                  await addLog.mutateAsync({
                    description: logForm.description,
                    date_performed: today(),
                    next_due_date: logForm.next_due_date || null,
                    cost: logForm.cost || null,
                  })
                  toastOk('The work is recorded.')
                  setLogOpen(false)
                  setLogForm({ description: '', next_due_date: '', cost: '' })
                } catch (failure) {
                  toastError(failure)
                }
              }}
            >
              Save
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Field label="What was done">
            <Textarea
              rows={2}
              value={logForm.description}
              onChange={(event) => setLogForm({ ...logForm, description: event.target.value })}
              placeholder="Changed the oil and the filter"
            />
          </Field>
          <Field label="Next due">
            <Input
              type="date"
              value={logForm.next_due_date}
              onChange={(event) => setLogForm({ ...logForm, next_due_date: event.target.value })}
            />
          </Field>
          <Field label="Cost">
            <Input
              inputMode="decimal"
              value={logForm.cost}
              onChange={(event) => setLogForm({ ...logForm, cost: event.target.value })}
              placeholder="89.00"
            />
          </Field>
        </div>
      </Modal>

      <Modal open={qrOpen} title="Label for this item" onClose={() => setQrOpen(false)}>
        <div className="flex flex-col items-center gap-3">
          <QrImage
            path={`/api/items/${item.id}/qr?size=320`}
            alt={`QR code for ${item.name}`}
            className="rounded-lg border border-ink-200 dark:border-ink-800"
          />
          <p className="text-center text-sm text-ink-500">
            The code opens this page. Print it and stick it on the item.
          </p>
          <Button onClick={() => window.print()}>Print</Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this item?"
        message="The item goes away from every list. The mobile application learns about it on the next sync."
        loading={remove.isPending}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          try {
            await remove.mutateAsync(id)
            toastOk('The item is deleted.')
            navigate('/items')
          } catch (failure) {
            toastError(failure)
          }
        }}
      />
    </div>
  )
}
