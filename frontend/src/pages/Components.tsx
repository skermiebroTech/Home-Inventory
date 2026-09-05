/** The component catalogue: what a part is, and what one costs. */

import { Cog, Package, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { mediaUrl } from '@/api/client'
import type { Component, ComponentWrite } from '@/api/types'
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
import PhotoStrip from '@/components/PhotoStrip'
import {
  useComponent,
  useComponents,
  useCreateComponent,
  useDeleteComponent,
  useUpdateComponent,
} from '@/hooks/useComponents'
import { formatMoney } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

function emptyDraft(): ComponentWrite {
  return {
    name: '',
    brand: null,
    model_number: null,
    category: null,
    description: null,
    default_price: null,
    is_consumable: false,
  }
}

export default function Components() {
  const [search, setSearch] = useState('')
  const [onlyConsumable, setOnlyConsumable] = useState<boolean | undefined>(undefined)
  const { data, isLoading } = useComponents({
    q: search || undefined,
    consumable: onlyConsumable,
  })
  const create = useCreateComponent()
  const update = useUpdateComponent()
  const remove = useDeleteComponent()

  const [draft, setDraft] = useState<(ComponentWrite & { id?: string }) | null>(null)
  const [doomed, setDoomed] = useState<Component | null>(null)
  const [inspecting, setInspecting] = useState<string | null>(null)

  const save = async () => {
    if (!draft) return
    const { id, ...body } = draft
    try {
      if (id) await update.mutateAsync({ id, body })
      else await create.mutateAsync(body)
      toastOk('The component is saved.')
      setDraft(null)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div>
      <PageHeader
        title="Components"
        subtitle="The parts that your items are made of, and what each one costs."
        action={
          <Button onClick={() => setDraft(emptyDraft())} icon={<Plus className="h-4 w-4" />}>
            Add a component
          </Button>
        }
      />

      <Card className="mb-4 flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <Field label="Search">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Name, brand, or model number"
            />
          </Field>
        </div>
        <Field label="Kind">
          <Select
            value={onlyConsumable === undefined ? '' : String(onlyConsumable)}
            onChange={(event) =>
              setOnlyConsumable(
                event.target.value === '' ? undefined : event.target.value === 'true',
              )
            }
            className="w-44"
          >
            <option value="">Every component</option>
            <option value="true">Consumables only</option>
            <option value="false">Lasting parts only</option>
          </Select>
        </Field>
      </Card>

      {isLoading ? <Loading /> : null}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<Cog className="h-8 w-8" />}
          title="No component yet"
          hint="A battery, a filter, a blade, a belt. Add it once, then fit it to as many items as you like."
        />
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data?.map((component) => (
          <Card key={component.id} className="flex flex-col gap-2">
            <div className="flex items-start justify-between gap-2">
              {component.thumbnail_path ? (
                <img
                  src={mediaUrl(component.thumbnail_path)}
                  alt=""
                  loading="lazy"
                  className="h-12 w-12 shrink-0 rounded-lg border border-ink-200 object-cover dark:border-ink-800"
                />
              ) : null}
              <div className="min-w-0 flex-1">
                <button
                  onClick={() => setInspecting(component.id)}
                  className="truncate text-left text-sm font-medium hover:underline"
                >
                  {component.name}
                </button>
                <p className="truncate text-xs text-ink-500">
                  {[component.brand, component.model_number].filter(Boolean).join(' · ') ||
                    'No brand or model'}
                </p>
              </div>
              {component.is_consumable ? (
                <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  consumable
                </Badge>
              ) : null}
            </div>

            <p className="text-sm">
              {component.default_price
                ? `${formatMoney(component.default_price)} each`
                : 'No default price'}
            </p>

            <div className="mt-auto flex gap-2 pt-1">
              <button
                onClick={() =>
                  setDraft({
                    id: component.id,
                    name: component.name,
                    brand: component.brand,
                    model_number: component.model_number,
                    category: component.category,
                    description: component.description,
                    default_price: component.default_price,
                    is_consumable: component.is_consumable,
                  })
                }
                className="inline-flex items-center gap-1 text-xs text-ink-500 hover:text-ink-900 dark:hover:text-ink-100"
              >
                <Pencil className="h-3.5 w-3.5" /> Edit
              </button>
              <button
                onClick={() => setDoomed(component)}
                className="inline-flex items-center gap-1 text-xs text-red-500 hover:text-red-700"
              >
                <Trash2 className="h-3.5 w-3.5" /> Delete
              </button>
            </div>
          </Card>
        ))}
      </div>

      <Modal
        open={draft !== null}
        title={draft?.id ? 'Edit the component' : 'Add a component'}
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
                autoFocus
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                placeholder="DeWalt DCB184 battery"
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Brand">
                <Input
                  value={draft.brand ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, brand: event.target.value || null })
                  }
                />
              </Field>
              <Field label="Model number">
                <Input
                  value={draft.model_number ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, model_number: event.target.value || null })
                  }
                  placeholder="DCB184"
                />
              </Field>
              <Field label="Category">
                <Input
                  value={draft.category ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, category: event.target.value || null })
                  }
                  placeholder="Batteries"
                />
              </Field>
              <Field label="Default price" hint="Used when a fitted part names no price.">
                <Input
                  inputMode="decimal"
                  value={draft.default_price ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, default_price: event.target.value || null })
                  }
                  placeholder="119.00"
                />
              </Field>
            </div>
            <Field label="Description">
              <Textarea
                rows={2}
                value={draft.description ?? ''}
                onChange={(event) =>
                  setDraft({ ...draft, description: event.target.value || null })
                }
              />
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={draft.is_consumable ?? false}
                onChange={(event) =>
                  setDraft({ ...draft, is_consumable: event.target.checked })
                }
                className="h-4 w-4 rounded border-ink-300"
              />
              This runs out and gets replaced, such as a filter or a blade.
            </label>

            {draft.id ? (
              <div>
                <span className="label">Photographs</span>
                <PhotoStrip owner="components" ownerId={draft.id} />
              </div>
            ) : (
              <p className="text-xs text-ink-500">
                Save the component first. Then you can add photographs.
              </p>
            )}
          </div>
        ) : null}
      </Modal>

      <ComponentUses id={inspecting} onClose={() => setInspecting(null)} />

      <ConfirmDialog
        open={doomed !== null}
        title={`Delete ${doomed?.name ?? 'this component'}?`}
        message="Any spares of it go too. An item that still carries it keeps it, and the delete is refused."
        loading={remove.isPending}
        onCancel={() => setDoomed(null)}
        onConfirm={async () => {
          if (!doomed) return
          try {
            await remove.mutateAsync(doomed.id)
            toastOk('The component is deleted.')
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

/** Where one component is used, and how many are on the shelf. */
function ComponentUses({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { data, isLoading } = useComponent(id ?? undefined)

  return (
    <Modal open={id !== null} title={data?.name ?? 'Component'} onClose={onClose}>
      {isLoading ? <Loading /> : null}
      {data ? (
        <div className="space-y-3 text-sm">
          <p className="text-ink-500">
            {[data.brand, data.model_number].filter(Boolean).join(' · ') || 'No brand'}
            {data.default_price ? ` · ${formatMoney(data.default_price)} each` : ''}
          </p>

          <div className="flex gap-4">
            <span className="inline-flex items-center gap-1">
              <Cog className="h-4 w-4 text-ink-400" /> {data.fitted_count} fitted
            </span>
            <span className="inline-flex items-center gap-1">
              <Package className="h-4 w-4 text-ink-400" /> {data.spare_quantity} spare
            </span>
          </div>

          {data.fitted_to.length > 0 ? (
            <div>
              <p className="label">Fitted to</p>
              <ul className="space-y-1">
                {data.fitted_to.map((use) => (
                  <li key={use.item_id} className="flex justify-between">
                    <a
                      href={`/items/${use.item_id}`}
                      className="text-accent-600 hover:underline dark:text-accent-400"
                    >
                      {use.item_name}
                    </a>
                    <span className="text-ink-500">{use.quantity}×</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-ink-500">No item carries this component yet.</p>
          )}

          {data.description ? <p>{data.description}</p> : null}
        </div>
      ) : null}
    </Modal>
  )
}
