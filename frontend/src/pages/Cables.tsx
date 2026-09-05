/**
 * The cables drawer.
 *
 * One question sends a person to this page: "do I have a cable with USB-C on
 * one end?" The search box asks that question, and the connector buttons ask
 * it with one click.
 */

import { Cable as CableIcon, Plus, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'

import type { Cable, CableWrite } from '@/api/types'
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
  Textarea,
} from '@/components/ui'
import {
  useCableKinds,
  useCables,
  useCreateCable,
  useDeleteCable,
  useUpdateCable,
} from '@/hooks/useCables'
import { useItems } from '@/hooks/useItems'
import { cx, formatMoney } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

/** The ends that a house has most of. The field still takes any words. */
const COMMON_ENDS = [
  'USB-C',
  'USB-A',
  'Micro-USB',
  'Lightning',
  'HDMI',
  'DisplayPort',
  'RJ45',
  'IEC C13',
  '3.5 mm',
  'DC barrel',
]

function emptyDraft(): CableWrite {
  return {
    name: '',
    kind: null,
    connector_a: null,
    connector_b: null,
    length_cm: null,
    colour: null,
    brand: null,
    specification: null,
    quantity: 1,
    price: null,
    notes: null,
    location_id: null,
    item_id: null,
  }
}

function toDraft(cable: Cable): CableWrite & { id: string } {
  return {
    id: cable.id,
    name: cable.name,
    kind: cable.kind,
    connector_a: cable.connector_a,
    connector_b: cable.connector_b,
    length_cm: cable.length_cm,
    colour: cable.colour,
    brand: cable.brand,
    specification: cable.specification,
    quantity: cable.quantity,
    price: cable.price,
    notes: cable.notes,
    location_id: cable.location_id,
    item_id: cable.item_id,
  }
}

export default function Cables() {
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('')
  const [connector, setConnector] = useState('')

  const { data, isLoading } = useCables({
    q: search.trim() || undefined,
    kind: kind || undefined,
    connector: connector || undefined,
  })
  const { data: kinds } = useCableKinds()
  const { data: itemPage } = useItems({ per_page: 200, sort: 'name' })
  const create = useCreateCable()
  const update = useUpdateCable()
  const remove = useDeleteCable()

  const [draft, setDraft] = useState<(CableWrite & { id?: string }) | null>(null)
  const [doomed, setDoomed] = useState<Cable | null>(null)

  const rows = data ?? []
  const total = rows.reduce((sum, row) => sum + row.quantity, 0)

  const save = async () => {
    if (!draft) return
    const { id, ...body } = draft
    try {
      if (id) await update.mutateAsync({ id, body })
      else await create.mutateAsync(body)
      toastOk('The cable is saved.')
      setDraft(null)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div>
      <PageHeader
        title="Cables"
        subtitle="Every lead in the house, with both ends and the length."
        action={
          <Button onClick={() => setDraft(emptyDraft())} icon={<Plus className="h-4 w-4" />}>
            Add a cable
          </Button>
        }
      />

      <Card className="mb-4 space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-56 flex-1">
            <Field label="Search">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="A name, a brand, or an end"
                  className="pl-9"
                />
              </div>
            </Field>
          </div>

          <Field label="Family">
            <Select
              value={kind}
              onChange={(event) => setKind(event.target.value)}
              className="w-44"
            >
              <option value="">Every family</option>
              {(kinds ?? []).map((row) => (
                <option key={row} value={row}>
                  {row}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-500">One end is:</span>
          {COMMON_ENDS.map((end) => (
            <button
              key={end}
              onClick={() => setConnector(connector === end ? '' : end)}
              className={cx(
                'rounded-full border px-2.5 py-1 text-xs transition',
                connector === end
                  ? 'border-accent-500 bg-accent-500 text-white'
                  : 'border-ink-200 text-ink-600 hover:border-ink-400 dark:border-ink-700 dark:text-ink-300',
              )}
            >
              {end}
            </button>
          ))}
        </div>
      </Card>

      {isLoading ? <Loading /> : null}

      {data && rows.length === 0 ? (
        <EmptyState
          icon={<CableIcon className="h-8 w-8" />}
          title="No cable answers that"
          hint={
            search || kind || connector
              ? 'Clear the search and the filters to see them all.'
              : 'Add the leads in the drawer. Then you never buy a second one.'
          }
        />
      ) : null}

      {rows.length > 0 ? (
        <>
          <p className="mb-2 text-xs text-ink-500">
            {rows.length} {rows.length === 1 ? 'entry' : 'entries'}, {total} in the
            drawer.
          </p>
          <Card className="p-0">
            {rows.map((cable) => (
              <div
                key={cable.id}
                className="flex flex-wrap items-center gap-3 border-b border-ink-200 px-4 py-3 last:border-0 dark:border-ink-800"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {cable.quantity > 1 ? `${cable.quantity}x ` : ''}
                    {cable.name}
                    {cable.kind ? <Badge className="ml-2">{cable.kind}</Badge> : null}
                  </p>
                  <p className="truncate text-xs text-ink-500">
                    {[cable.ends, cable.length_label, cable.specification, cable.colour]
                      .filter(Boolean)
                      .join(' · ') || 'No details recorded'}
                  </p>
                  {cable.notes ? (
                    <p className="truncate text-xs text-ink-500">{cable.notes}</p>
                  ) : null}
                </div>

                <div className="text-right text-xs text-ink-500">
                  <p>{cable.location_name ?? 'No place recorded'}</p>
                  <p>
                    {cable.item_name ? `For the ${cable.item_name}` : 'Spare lead'}
                    {cable.total_value ? ` · ${formatMoney(cable.total_value)}` : ''}
                  </p>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setDraft(toDraft(cable))}
                    className="px-1 text-xs text-ink-500 hover:text-ink-900 dark:hover:text-ink-100"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => setDoomed(cable)}
                    aria-label={`Delete ${cable.name}`}
                    className="rounded p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-950/50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </Card>
        </>
      ) : null}

      <Modal
        open={draft !== null}
        title={draft?.id ? 'Change the cable' : 'Add a cable'}
        onClose={() => setDraft(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDraft(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => void save()}
              loading={create.isPending || update.isPending}
              disabled={!draft?.name.trim()}
            >
              Save
            </Button>
          </>
        }
      >
        {draft ? (
          <div className="space-y-3">
            <Field label="Name">
              <Input
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                placeholder="USB-C to HDMI, 2 m"
              />
            </Field>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="One end">
                <Input
                  list="cable-ends"
                  value={draft.connector_a ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, connector_a: event.target.value || null })
                  }
                />
              </Field>
              <Field label="The other end">
                <Input
                  list="cable-ends"
                  value={draft.connector_b ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, connector_b: event.target.value || null })
                  }
                />
              </Field>
            </div>
            <datalist id="cable-ends">
              {COMMON_ENDS.map((end) => (
                <option key={end} value={end} />
              ))}
            </datalist>

            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Length in cm">
                <Input
                  type="number"
                  min={0}
                  value={draft.length_cm ?? ''}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      length_cm: event.target.value ? Number(event.target.value) : null,
                    })
                  }
                />
              </Field>
              <Field label="How many">
                <Input
                  type="number"
                  min={0}
                  value={draft.quantity ?? 1}
                  onChange={(event) =>
                    setDraft({ ...draft, quantity: Number(event.target.value) })
                  }
                />
              </Field>
              <Field label="What one cost">
                <Input
                  inputMode="decimal"
                  value={draft.price ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, price: event.target.value || null })
                  }
                />
              </Field>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Family" hint="USB, Video, Network, Power.">
                <Input
                  list="cable-kinds"
                  value={draft.kind ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, kind: event.target.value || null })
                  }
                />
                <datalist id="cable-kinds">
                  {(kinds ?? []).map((row) => (
                    <option key={row} value={row} />
                  ))}
                </datalist>
              </Field>
              <Field label="Brand">
                <Input
                  value={draft.brand ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, brand: event.target.value || null })
                  }
                />
              </Field>
              <Field label="Colour">
                <Input
                  value={draft.colour ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, colour: event.target.value || null })
                  }
                />
              </Field>
            </div>

            <Field label="What it can do" hint="USB 3.2, 10 Gbps, 100 W. Or Cat6a.">
              <Input
                value={draft.specification ?? ''}
                onChange={(event) =>
                  setDraft({ ...draft, specification: event.target.value || null })
                }
              />
            </Field>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Where it is">
                <LocationSelect
                  value={draft.location_id ?? null}
                  onChange={(id) => setDraft({ ...draft, location_id: id })}
                />
              </Field>
              <Field label="The device it came with">
                <Select
                  value={draft.item_id ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, item_id: event.target.value || null })
                  }
                >
                  <option value="">No device</option>
                  {(itemPage?.items ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field label="Notes">
              <Textarea
                rows={2}
                value={draft.notes ?? ''}
                onChange={(event) =>
                  setDraft({ ...draft, notes: event.target.value || null })
                }
              />
            </Field>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={doomed !== null}
        title={`Delete ${doomed?.name ?? ''}?`}
        message="The cable goes from the list. Nothing else changes."
        confirmLabel="Delete"
        loading={remove.isPending}
        onCancel={() => setDoomed(null)}
        onConfirm={async () => {
          if (!doomed) return
          try {
            await remove.mutateAsync(doomed.id)
            toastOk('The cable is deleted.')
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
