/** The location dropdown and the tag chooser. Both read small cached lists. */

import { Check, Plus } from 'lucide-react'
import { useState } from 'react'

import type { Tag } from '@/api/types'
import { flattenTree, useCreateTag, useLocationTree, useTags } from '@/hooks/useCatalogue'
import { cx } from '@/lib/format'
import { toastError } from '@/store/toast'
import { Badge, Button, Input, Select } from './ui'

export function LocationSelect({
  value,
  onChange,
  allowEmpty = true,
  exclude,
  id,
}: {
  value: string | null
  onChange: (id: string | null) => void
  allowEmpty?: boolean
  exclude?: string
  id?: string
}) {
  const { data } = useLocationTree()
  const rows = flattenTree(data ?? []).filter((row) => row.id !== exclude)

  return (
    <Select
      id={id}
      value={value ?? ''}
      onChange={(event) => onChange(event.target.value || null)}
    >
      {allowEmpty ? <option value="">No location</option> : null}
      {rows.map((row) => (
        <option key={row.id} value={row.id}>
          {' '.repeat(row.depth * 2)}
          {row.node.name}
        </option>
      ))}
    </Select>
  )
}

export function TagPicker({
  selected,
  onChange,
}: {
  selected: string[]
  onChange: (ids: string[]) => void
}) {
  const { data: tags } = useTags()
  const createTag = useCreateTag()
  const [newName, setNewName] = useState('')

  const toggle = (tag: Tag) => {
    onChange(
      selected.includes(tag.id)
        ? selected.filter((id) => id !== tag.id)
        : [...selected, tag.id],
    )
  }

  const add = async () => {
    const name = newName.trim()
    if (!name) return
    try {
      const tag = await createTag.mutateAsync({ name })
      onChange([...selected, tag.id])
      setNewName('')
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {(tags ?? []).map((tag) => {
          const active = selected.includes(tag.id)
          return (
            <button
              key={tag.id}
              type="button"
              onClick={() => toggle(tag)}
              className={cx(
                'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors',
                active
                  ? 'border-transparent text-white'
                  : 'border-ink-300 text-ink-600 hover:bg-ink-100 dark:border-ink-700 dark:text-ink-300 dark:hover:bg-ink-800',
              )}
              style={active ? { backgroundColor: tag.color } : undefined}
            >
              {active ? <Check className="h-3 w-3" /> : null}
              {tag.name}
            </button>
          )
        })}
        {(tags ?? []).length === 0 ? (
          <span className="text-xs text-ink-500">No tags yet.</span>
        ) : null}
      </div>

      <div className="flex gap-2">
        <Input
          value={newName}
          placeholder="New tag"
          onChange={(event) => setNewName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              void add()
            }
          }}
        />
        <Button
          type="button"
          variant="secondary"
          onClick={() => void add()}
          loading={createTag.isPending}
          icon={<Plus className="h-4 w-4" />}
        >
          Add
        </Button>
      </div>
    </div>
  )
}

export function TagList({ tags }: { tags: Tag[] }) {
  if (tags.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag.id} color={tag.color}>
          {tag.name}
        </Badge>
      ))}
    </div>
  )
}
