/** What one item is made of: the parts fitted to it. */

import { Cog, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import type { ItemComponent, ItemComponentWrite } from '@/api/types'
import {
  Badge,
  Button,
  ConfirmDialog,
  Field,
  Input,
  Loading,
  Modal,
  Select,
  Textarea,
} from '@/components/ui'
import {
  useComponents,
  useFitComponent,
  useItemComponents,
  useRemoveFitted,
  useUpdateFitted,
} from '@/hooks/useComponents'
import { formatDate, formatMoney } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

interface Draft extends ItemComponentWrite {
  id?: string
}

function emptyDraft(): Draft {
  return {
    component_id: '',
    quantity: 1,
    price: null,
    serial_number: null,
    fitted_on: null,
    notes: null,
  }
}

export default function ItemComponents({ itemId }: { itemId: string }) {
  const { data, isLoading } = useItemComponents(itemId)
  const { data: catalogue } = useComponents()
  const fit = useFitComponent(itemId)
  const update = useUpdateFitted(itemId)
  const remove = useRemoveFitted(itemId)

  const [draft, setDraft] = useState<Draft | null>(null)
  const [doomed, setDoomed] = useState<ItemComponent | null>(null)

  const total = (data ?? []).reduce(
    (sum, entry) => sum + Number.parseFloat(entry.line_total ?? '0'),
    0,
  )

  const save = async () => {
    if (!draft) return
    const { id, component_id, ...rest } = draft
    try {
      if (id) await update.mutateAsync({ id, body: rest })
      else await fit.mutateAsync({ component_id, ...rest })
      toastOk('The component is saved.')
      setDraft(null)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Cog className="h-4 w-4 text-ink-400" /> Components
          {total > 0 ? (
            <span className="font-normal text-ink-500">· {formatMoney(total)}</span>
          ) : null}
        </h2>
        <Button
          variant="secondary"
          onClick={() => setDraft(emptyDraft())}
          icon={<Plus className="h-4 w-4" />}
          disabled={(catalogue ?? []).length === 0}
          title={
            (catalogue ?? []).length === 0
              ? 'Add a component to the catalogue first.'
              : undefined
          }
        >
          Fit one
        </Button>
      </div>

      {isLoading ? <Loading /> : null}

      {data && data.length === 0 ? (
        <p className="text-sm text-ink-500">
          Nothing fitted yet. A battery, a filter, a blade: record it here and the
          value of the parts adds up.
        </p>
      ) : null}

      <ul className="space-y-2">
        {data?.map((entry) => (
          <li
            key={entry.id}
            className="rounded-lg border border-ink-200 p-3 text-sm dark:border-ink-800"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {entry.quantity > 1 ? `${entry.quantity}× ` : ''}
                  {entry.name}
                  {entry.is_consumable ? (
                    <Badge className="ml-2 bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                      consumable
                    </Badge>
                  ) : null}
                </p>
                <p className="text-xs text-ink-500">
                  {[entry.brand, entry.model_number].filter(Boolean).join(' · ') ||
                    'No brand or model'}
                  {entry.serial_number ? ` · serial ${entry.serial_number}` : ''}
                  {entry.fitted_on ? ` · fitted ${formatDate(entry.fitted_on)}` : ''}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-medium">{formatMoney(entry.line_total)}</p>
                <p className="text-xs text-ink-500">
                  {entry.price === null ? 'default price' : 'own price'}
                </p>
              </div>
            </div>

            {entry.notes ? (
              <p className="mt-1 whitespace-pre-line text-ink-600 dark:text-ink-300">
                {entry.notes}
              </p>
            ) : null}

            <div className="mt-2 flex gap-3">
              <button
                onClick={() =>
                  setDraft({
                    id: entry.id,
                    component_id: entry.component_id,
                    quantity: entry.quantity,
                    price: entry.price,
                    serial_number: entry.serial_number,
                    fitted_on: entry.fitted_on,
                    notes: entry.notes,
                  })
                }
                className="text-xs text-ink-500 hover:text-ink-900 dark:hover:text-ink-100"
              >
                Edit
              </button>
              <button
                onClick={() => setDoomed(entry)}
                className="inline-flex items-center gap-1 text-xs text-red-500 hover:text-red-700"
              >
                <Trash2 className="h-3.5 w-3.5" /> Take off
              </button>
            </div>
          </li>
        ))}
      </ul>

      <Modal
        open={draft !== null}
        title={draft?.id ? 'Change the fitted component' : 'Fit a component'}
        onClose={() => setDraft(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDraft(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => void save()}
              loading={fit.isPending || update.isPending}
              disabled={!draft?.component_id}
            >
              Save
            </Button>
          </>
        }
      >
        {draft ? (
          <div className="space-y-3">
            <Field label="Component">
              <Select
                value={draft.component_id}
                disabled={Boolean(draft.id)}
                onChange={(event) =>
                  setDraft({ ...draft, component_id: event.target.value })
                }
              >
                <option value="">Choose a component</option>
                {(catalogue ?? []).map((component) => (
                  <option key={component.id} value={component.id}>
                    {component.name}
                    {component.default_price
                      ? ` — ${formatMoney(component.default_price)}`
                      : ''}
                  </option>
                ))}
              </Select>
            </Field>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="How many">
                <Input
                  type="number"
                  min={1}
                  value={draft.quantity ?? 1}
                  onChange={(event) =>
                    setDraft({ ...draft, quantity: Number(event.target.value) })
                  }
                />
              </Field>
              <Field label="Price for this one" hint="Empty means the default price.">
                <Input
                  inputMode="decimal"
                  value={draft.price ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, price: event.target.value || null })
                  }
                />
              </Field>
              <Field label="Serial number">
                <Input
                  value={draft.serial_number ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, serial_number: event.target.value || null })
                  }
                />
              </Field>
              <Field label="Fitted on">
                <Input
                  type="date"
                  value={draft.fitted_on ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, fitted_on: event.target.value || null })
                  }
                />
              </Field>
            </div>

            <Field label="Notes">
              <Textarea
                rows={2}
                value={draft.notes ?? ''}
                onChange={(event) =>
                  setDraft({ ...draft, notes: event.target.value || null })
                }
                placeholder="Where it came from, how it behaves, when to change it."
              />
            </Field>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={doomed !== null}
        title={`Take the ${doomed?.name ?? 'component'} off?`}
        message="The component stays in the catalogue. Only the record of it on this item goes."
        confirmLabel="Take off"
        loading={remove.isPending}
        onCancel={() => setDoomed(null)}
        onConfirm={async () => {
          if (!doomed) return
          try {
            await remove.mutateAsync(doomed.id)
            toastOk('The component is off the item.')
          } catch (error) {
            toastError(error)
          } finally {
            setDoomed(null)
          }
        }}
      />
    </div>
  )
}
