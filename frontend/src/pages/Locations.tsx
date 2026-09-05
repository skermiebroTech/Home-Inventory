/** The location tree. Rooms hold zones, and zones hold containers. */

import {
  ChevronDown,
  ChevronRight,
  MapPinned,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { LocationNode, LocationType } from '@/api/types'
import { LocationSelect } from '@/components/pickers'
import {
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
  useCreateLocation,
  useDeleteLocation,
  useLocationTree,
  useUpdateLocation,
} from '@/hooks/useCatalogue'
import { cx } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

const TYPES: LocationType[] = ['room', 'zone', 'container']

interface Draft {
  id?: string
  name: string
  type: LocationType
  parent_id: string | null
  description: string
}

function emptyDraft(parent: string | null = null): Draft {
  return { name: '', type: 'room', parent_id: parent, description: '' }
}

function Node({
  node,
  depth,
  onEdit,
  onAddChild,
  onDelete,
}: {
  node: LocationNode
  depth: number
  onEdit: (node: LocationNode) => void
  onAddChild: (node: LocationNode) => void
  onDelete: (node: LocationNode) => void
}) {
  const [open, setOpen] = useState(depth < 2)
  const hasChildren = node.children.length > 0

  return (
    <li>
      <div
        className="group flex items-center gap-1 rounded-lg px-2 py-1.5 hover:bg-ink-100 dark:hover:bg-ink-800"
        style={{ paddingLeft: `${depth * 18 + 8}px` }}
      >
        <button
          onClick={() => setOpen((value) => !value)}
          className={cx('rounded p-0.5 text-ink-400', !hasChildren && 'invisible')}
          aria-label={open ? 'Collapse' : 'Expand'}
        >
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </button>

        <Link to={`/items?location_id=${node.id}`} className="min-w-0 flex-1 truncate text-sm">
          {node.name}
          <span className="ml-2 text-xs uppercase tracking-wide text-ink-400">{node.type}</span>
        </Link>

        {node.item_count > 0 ? (
          <span className="shrink-0 text-xs text-ink-500">{node.item_count} items</span>
        ) : null}

        <div className="flex shrink-0 gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <button
            onClick={() => onAddChild(node)}
            aria-label={`Add a location inside ${node.name}`}
            className="rounded p-1 text-ink-500 hover:bg-ink-200 dark:hover:bg-ink-700"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => onEdit(node)}
            aria-label={`Edit ${node.name}`}
            className="rounded p-1 text-ink-500 hover:bg-ink-200 dark:hover:bg-ink-700"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => onDelete(node)}
            aria-label={`Delete ${node.name}`}
            className="rounded p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-950/50"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {open && hasChildren ? (
        <ul>
          {node.children.map((child) => (
            <Node
              key={child.id}
              node={child}
              depth={depth + 1}
              onEdit={onEdit}
              onAddChild={onAddChild}
              onDelete={onDelete}
            />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

export default function Locations() {
  const { data, isLoading } = useLocationTree()
  const create = useCreateLocation()
  const update = useUpdateLocation()
  const remove = useDeleteLocation()

  const [draft, setDraft] = useState<Draft | null>(null)
  const [doomed, setDoomed] = useState<LocationNode | null>(null)

  const save = async () => {
    if (!draft) return
    const body = {
      name: draft.name.trim(),
      type: draft.type,
      parent_id: draft.parent_id,
      description: draft.description || null,
    }
    try {
      if (draft.id) await update.mutateAsync({ id: draft.id, body })
      else await create.mutateAsync(body)
      toastOk('The location is saved.')
      setDraft(null)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div>
      <PageHeader
        title="Locations"
        subtitle="A room holds zones. A zone holds containers."
        action={
          <Button onClick={() => setDraft(emptyDraft())} icon={<Plus className="h-4 w-4" />}>
            Add a location
          </Button>
        }
      />

      {isLoading ? <Loading /> : null}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<MapPinned className="h-8 w-8" />}
          title="No location yet"
          hint="Start with a room. Then add the shelves and boxes inside it."
          action={<Button onClick={() => setDraft(emptyDraft())}>Add a room</Button>}
        />
      ) : null}

      {data && data.length > 0 ? (
        <Card className="p-2">
          <ul>
            {data.map((node) => (
              <Node
                key={node.id}
                node={node}
                depth={0}
                onEdit={(entry) =>
                  setDraft({
                    id: entry.id,
                    name: entry.name,
                    type: entry.type,
                    parent_id: entry.parent_id,
                    description: entry.description ?? '',
                  })
                }
                onAddChild={(entry) =>
                  setDraft({
                    ...emptyDraft(entry.id),
                    type: entry.type === 'room' ? 'zone' : 'container',
                  })
                }
                onDelete={setDoomed}
              />
            ))}
          </ul>
        </Card>
      ) : null}

      <Modal
        open={draft !== null}
        title={draft?.id ? 'Edit the location' : 'Add a location'}
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
                placeholder="Garage"
              />
            </Field>
            <Field label="Type">
              <Select
                value={draft.type}
                onChange={(event) => setDraft({ ...draft, type: event.target.value as LocationType })}
              >
                {TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Inside" hint="Leave empty to put it at the top.">
              <LocationSelect
                value={draft.parent_id}
                exclude={draft.id}
                onChange={(id) => setDraft({ ...draft, parent_id: id })}
              />
            </Field>
            <Field label="Description">
              <Textarea
                rows={2}
                value={draft.description}
                onChange={(event) => setDraft({ ...draft, description: event.target.value })}
              />
            </Field>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={doomed !== null}
        title={`Delete ${doomed?.name ?? 'this location'}?`}
        message="Every location inside it goes too. The items stay, and they become unplaced."
        loading={remove.isPending}
        onCancel={() => setDoomed(null)}
        onConfirm={async () => {
          if (!doomed) return
          try {
            const result = await remove.mutateAsync(doomed.id)
            toastOk(result.message)
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
