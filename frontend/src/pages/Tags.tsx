import { Boxes, Plus, Tags as TagsIcon, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { Tag } from '@/api/types'
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
} from '@/components/ui'
import { useCreateTag, useDeleteTag, useTags, useUpdateTag } from '@/hooks/useCatalogue'
import { toastError, toastOk } from '@/store/toast'

const PALETTE = [
  '#64748b',
  '#ef4444',
  '#f97316',
  '#eab308',
  '#22c55e',
  '#06b6d4',
  '#3b82f6',
  '#8b5cf6',
  '#ec4899',
]

export default function TagsPage() {
  const { data, isLoading } = useTags()
  const create = useCreateTag()
  const update = useUpdateTag()
  const remove = useDeleteTag()

  const [draft, setDraft] = useState<{ id?: string; name: string; color: string } | null>(null)
  const [doomed, setDoomed] = useState<Tag | null>(null)

  const save = async () => {
    if (!draft) return
    try {
      if (draft.id) {
        await update.mutateAsync({ id: draft.id, body: { name: draft.name, color: draft.color } })
      } else {
        await create.mutateAsync({ name: draft.name, color: draft.color })
      }
      toastOk('The tag is saved.')
      setDraft(null)
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div>
      <PageHeader
        title="Tags"
        subtitle="A tag groups items across rooms."
        action={
          <Button
            onClick={() => setDraft({ name: '', color: PALETTE[0] as string })}
            icon={<Plus className="h-4 w-4" />}
          >
            Add a tag
          </Button>
        }
      />

      {isLoading ? <Loading /> : null}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<TagsIcon className="h-8 w-8" />}
          title="No tag yet"
          hint="Try Fragile, Warranty, or Camping."
        />
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data?.map((tag) => (
          <Card key={tag.id} className="flex items-center gap-3">
            <span
              className="h-8 w-8 shrink-0 rounded-full"
              style={{ backgroundColor: tag.color }}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{tag.name}</p>
              <Link
                to={`/items?tag_id=${tag.id}`}
                className="inline-flex items-center gap-1 text-xs text-accent-600 hover:underline dark:text-accent-400"
              >
                <Boxes className="h-3 w-3" /> See the items
              </Link>
            </div>
            <button
              onClick={() => setDraft({ id: tag.id, name: tag.name, color: tag.color })}
              className="text-xs text-ink-500 hover:text-ink-900 dark:hover:text-ink-100"
            >
              Edit
            </button>
            <button
              onClick={() => setDoomed(tag)}
              aria-label={`Delete ${tag.name}`}
              className="rounded p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-950/50"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </Card>
        ))}
      </div>

      <Modal
        open={draft !== null}
        title={draft?.id ? 'Edit the tag' : 'Add a tag'}
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
              />
            </Field>
            <div>
              <span className="label">Colour</span>
              <div className="flex flex-wrap gap-2">
                {PALETTE.map((colour) => (
                  <button
                    key={colour}
                    type="button"
                    onClick={() => setDraft({ ...draft, color: colour })}
                    aria-label={colour}
                    className={
                      draft.color === colour
                        ? 'h-8 w-8 rounded-full ring-2 ring-ink-900 ring-offset-2 dark:ring-ink-100 dark:ring-offset-ink-900'
                        : 'h-8 w-8 rounded-full'
                    }
                    style={{ backgroundColor: colour }}
                  />
                ))}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={doomed !== null}
        title={`Delete ${doomed?.name ?? 'this tag'}?`}
        message="The tag comes off every item. The items stay."
        loading={remove.isPending}
        onCancel={() => setDoomed(null)}
        onConfirm={async () => {
          if (!doomed) return
          try {
            await remove.mutateAsync(doomed.id)
            toastOk('The tag is deleted.')
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
