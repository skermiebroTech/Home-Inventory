/**
 * The spares shelf.
 *
 * Stock of a component that no item uses yet. What ran low comes first,
 * because that is the reason to open this page.
 */

import { AlertTriangle, Minus, Package, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import type { Spare, SpareWrite } from '@/api/types'
import { LocationSelect } from '@/components/pickers'
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  Loading,
  Modal,
  PageHeader,
  Select,
} from '@/components/ui'
import {
  useComponents,
  useCreateSpare,
  useDeleteSpare,
  useSpares,
  useUpdateSpare,
  useUseSpare,
} from '@/hooks/useComponents'
import { cx, formatMoney } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

function emptyDraft(): SpareWrite {
  return {
    component_id: '',
    quantity: 1,
    minimum_quantity: 0,
    location_id: null,
    unit_price: null,
    notes: null,
  }
}

export default function Spares() {
  const [filter, setFilter] = useState<'all' | 'low' | 'consumable'>('all')
  const { data, isLoading } = useSpares({
    low_only: filter === 'low' || undefined,
    consumable: filter === 'consumable' ? true : undefined,
  })
  const { data: catalogue } = useComponents()
  const create = useCreateSpare()
  const update = useUpdateSpare()
  const useOne = useUseSpare()
  const remove = useDeleteSpare()

  const [draft, setDraft] = useState<(SpareWrite & { id?: string }) | null>(null)
  const [doomed, setDoomed] = useState<Spare | null>(null)

  const lowCount = (data ?? []).filter((spare) => spare.is_low).length

  const save = async () => {
    if (!draft) return
    const { id, component_id, ...rest } = draft
    try {
      if (id) await update.mutateAsync({ id, body: rest })
      else await create.mutateAsync({ component_id, ...rest })
      toastOk('The stock is saved.')
      setDraft(null)
    } catch (error) {
      toastError(error)
    }
  }

  const adjust = async (spare: Spare, count: number) => {
    try {
      await useOne.mutateAsync({ id: spare.id, count })
      toastOk(count > 0 ? `One ${spare.name} used.` : `One ${spare.name} back on the shelf.`)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div>
      <PageHeader
        title="Spares"
        subtitle="Parts and consumables on the shelf, waiting for the day they are needed."
        action={
          <Button
            onClick={() => setDraft(emptyDraft())}
            icon={<Plus className="h-4 w-4" />}
            disabled={(catalogue ?? []).length === 0}
            title={
              (catalogue ?? []).length === 0
                ? 'Add a component to the catalogue first.'
                : undefined
            }
          >
            Add stock
          </Button>
        }
      />

      {lowCount > 0 ? (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {lowCount} {lowCount === 1 ? 'row has' : 'rows have'} reached the level you
          set. Time to buy more.
        </div>
      ) : null}

      <Card className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Show">
          <Select
            value={filter}
            onChange={(event) => setFilter(event.target.value as typeof filter)}
            className="w-52"
          >
            <option value="all">Everything on the shelf</option>
            <option value="low">Only what ran low</option>
            <option value="consumable">Only consumables</option>
          </Select>
        </Field>
      </Card>

      {isLoading ? <Loading /> : null}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<Package className="h-8 w-8" />}
          title="Nothing on the shelf"
          hint="Add the filters, blades, and batteries that you keep in reserve."
        />
      ) : null}

      {data && data.length > 0 ? (
        <Card className="p-0">
          {data.map((spare) => (
            <div
              key={spare.id}
              className={cx(
                'flex flex-wrap items-center gap-3 border-b border-ink-200 px-4 py-3 last:border-0 dark:border-ink-800',
                spare.is_low && 'bg-amber-50/60 dark:bg-amber-950/20',
              )}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {spare.name}
                  {spare.is_consumable ? (
                    <Badge className="ml-2 bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                      consumable
                    </Badge>
                  ) : null}
                </p>
                <p className="truncate text-xs text-ink-500">
                  {[spare.brand, spare.model_number, spare.location_name]
                    .filter(Boolean)
                    .join(' · ') || 'No place recorded'}
                </p>
              </div>

              <div className="text-right">
                <p
                  className={cx(
                    'text-sm font-medium',
                    spare.is_low && 'text-amber-700 dark:text-amber-400',
                  )}
                >
                  {spare.quantity} on the shelf
                </p>
                <p className="text-xs text-ink-500">
                  {spare.minimum_quantity > 0
                    ? `Buy more at ${spare.minimum_quantity}`
                    : 'No level set'}
                  {spare.stock_value ? ` · ${formatMoney(spare.stock_value)}` : ''}
                </p>
              </div>

              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  className="px-2"
                  aria-label={`Use one ${spare.name}`}
                  disabled={spare.quantity === 0}
                  onClick={() => void adjust(spare, 1)}
                >
                  <Minus className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  className="px-2"
                  aria-label={`Put one ${spare.name} back`}
                  onClick={() => void adjust(spare, -1)}
                >
                  <Plus className="h-4 w-4" />
                </Button>
                <button
                  onClick={() =>
                    setDraft({
                      id: spare.id,
                      component_id: spare.component_id,
                      quantity: spare.quantity,
                      minimum_quantity: spare.minimum_quantity,
                      location_id: spare.location_id,
                      unit_price: spare.unit_price,
                      notes: spare.notes,
                    })
                  }
                  className="px-1 text-xs text-ink-500 hover:text-ink-900 dark:hover:text-ink-100"
                >
                  Edit
                </button>
                <button
                  onClick={() => setDoomed(spare)}
                  aria-label={`Remove the ${spare.name} row`}
                  className="rounded p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-950/50"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </Card>
      ) : null}

      <Modal
        open={draft !== null}
        title={draft?.id ? 'Change the stock' : 'Add stock'}
        onClose={() => setDraft(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDraft(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => void save()}
              loading={create.isPending || update.isPending}
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
                  </option>
                ))}
              </Select>
            </Field>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="How many">
                <Input
                  type="number"
                  min={0}
                  value={draft.quantity ?? 0}
                  onChange={(event) =>
                    setDraft({ ...draft, quantity: Number(event.target.value) })
                  }
                />
              </Field>
              <Field label="Buy more at" hint="Zero turns the warning off.">
                <Input
                  type="number"
                  min={0}
                  value={draft.minimum_quantity ?? 0}
                  onChange={(event) =>
                    setDraft({ ...draft, minimum_quantity: Number(event.target.value) })
                  }
                />
              </Field>
            </div>

            <Field label="Where it is">
              <LocationSelect
                value={draft.location_id ?? null}
                onChange={(id) => setDraft({ ...draft, location_id: id })}
              />
            </Field>

            <Field label="What one cost" hint="Leave empty to use the default price.">
              <Input
                inputMode="decimal"
                value={draft.unit_price ?? ''}
                onChange={(event) =>
                  setDraft({ ...draft, unit_price: event.target.value || null })
                }
              />
            </Field>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={doomed !== null}
        title={`Remove the ${doomed?.name ?? ''} row?`}
        message="The component stays in the catalogue. Only this row of stock goes."
        confirmLabel="Remove"
        loading={remove.isPending}
        onCancel={() => setDoomed(null)}
        onConfirm={async () => {
          if (!doomed) return
          try {
            await remove.mutateAsync(doomed.id)
            toastOk('The row is removed.')
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
