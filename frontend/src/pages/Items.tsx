/** The item list: search, filters, and two views. */

import { Boxes, Filter, LayoutGrid, List, Plus, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import type { Condition, ItemQuery } from '@/api/types'
import { ItemGridCard, ItemRow } from '@/components/ItemCard'
import { LocationSelect } from '@/components/pickers'
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  Loading,
  PageHeader,
  Select,
} from '@/components/ui'
import { useTags } from '@/hooks/useCatalogue'
import { useOwners } from '@/hooks/usePhotos'
import { useItems } from '@/hooks/useItems'
import { cx } from '@/lib/format'

const SORTS: Array<{ value: string; label: string }> = [
  { value: '-created_at', label: 'Newest first' },
  { value: 'name', label: 'Name A to Z' },
  { value: '-current_value', label: 'Most valuable' },
  { value: '-updated_at', label: 'Recently changed' },
  { value: 'warranty_expires', label: 'Warranty ends soonest' },
]

export default function Items() {
  const [params, setParams] = useSearchParams()
  const { data: tags } = useTags()
  const { data: owners } = useOwners()
  const [view, setView] = useState<'grid' | 'list'>(() =>
    (localStorage.getItem('homestock-view') as 'grid' | 'list') ?? 'grid',
  )
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => localStorage.setItem('homestock-view', view), [view])

  const query = useMemo<ItemQuery>(() => {
    const tagId = params.getAll('tag_id')
    return {
      q: params.get('q') ?? undefined,
      location_id: params.get('location_id') ?? undefined,
      category: params.get('category') ?? undefined,
      condition: (params.get('condition') as Condition | null) ?? undefined,
      owner: params.get('owner') ?? undefined,
      is_lent: params.get('is_lent') ? params.get('is_lent') === 'true' : undefined,
      tag_id: tagId.length > 0 ? tagId : undefined,
      sort: params.get('sort') ?? '-created_at',
      page: Number(params.get('page') ?? 1),
      per_page: 24,
    }
  }, [params])

  const { data, isLoading, error, isFetching } = useItems(query)

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value === null || value === '') next.delete(key)
    else next.set(key, value)
    if (key !== 'page') next.delete('page')
    setParams(next)
  }

  const activeFilters = [
    'location_id',
    'category',
    'condition',
    'owner',
    'is_lent',
    'tag_id',
  ].filter(
    (key) => params.has(key),
  ).length

  return (
    <div>
      <PageHeader
        title="Items"
        subtitle={data ? `${data.total} items` : undefined}
        action={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => setShowFilters((open) => !open)}
              icon={<Filter className="h-4 w-4" />}
            >
              Filters{activeFilters ? ` (${activeFilters})` : ''}
            </Button>
            <div className="hidden rounded-lg border border-ink-300 sm:flex dark:border-ink-700">
              <button
                onClick={() => setView('grid')}
                aria-label="Grid view"
                className={cx('px-2.5 py-2', view === 'grid' && 'bg-ink-200 dark:bg-ink-800')}
              >
                <LayoutGrid className="h-4 w-4" />
              </button>
              <button
                onClick={() => setView('list')}
                aria-label="List view"
                className={cx('px-2.5 py-2', view === 'list' && 'bg-ink-200 dark:bg-ink-800')}
              >
                <List className="h-4 w-4" />
              </button>
            </div>
            <Link to="/items/new">
              <Button icon={<Plus className="h-4 w-4" />}>Add</Button>
            </Link>
          </div>
        }
      />

      {params.get('q') ? (
        <div className="mb-3 flex items-center gap-2 text-sm">
          <span className="text-ink-500">Search:</span>
          <span className="font-medium">{params.get('q')}</span>
          <button
            onClick={() => update('q', null)}
            className="rounded p-0.5 text-ink-500 hover:bg-ink-200 dark:hover:bg-ink-800"
            aria-label="Clear the search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : null}

      {showFilters ? (
        <Card className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Location">
            <LocationSelect
              value={params.get('location_id')}
              onChange={(id) => update('location_id', id)}
            />
          </Field>
          <Field label="Category">
            <input
              className="field"
              value={params.get('category') ?? ''}
              placeholder="Any"
              onChange={(event) => update('category', event.target.value || null)}
            />
          </Field>
          <Field label="Condition">
            <Select
              value={params.get('condition') ?? ''}
              onChange={(event) => update('condition', event.target.value || null)}
            >
              <option value="">Any</option>
              {['new', 'good', 'fair', 'poor'].map((entry) => (
                <option key={entry} value={entry}>
                  {entry}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Owner">
            <Select
              value={params.get('owner') ?? ''}
              onChange={(event) => update('owner', event.target.value || null)}
            >
              <option value="">Anyone</option>
              {(owners ?? []).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Lending">
            <Select
              value={params.get('is_lent') ?? ''}
              onChange={(event) => update('is_lent', event.target.value || null)}
            >
              <option value="">Any</option>
              <option value="true">Out on loan</option>
              <option value="false">Here</option>
            </Select>
          </Field>

          <div className="sm:col-span-2 lg:col-span-4">
            <span className="label">Tags</span>
            <div className="flex flex-wrap gap-1.5">
              {(tags ?? []).map((tag) => {
                const selected = params.getAll('tag_id').includes(tag.id)
                return (
                  <button
                    key={tag.id}
                    onClick={() => {
                      const next = new URLSearchParams(params)
                      const current = next.getAll('tag_id')
                      next.delete('tag_id')
                      const kept = selected
                        ? current.filter((id) => id !== tag.id)
                        : [...current, tag.id]
                      for (const id of kept) next.append('tag_id', id)
                      next.delete('page')
                      setParams(next)
                    }}
                    className={cx(
                      'rounded-full border px-2.5 py-1 text-xs',
                      selected
                        ? 'border-transparent text-white'
                        : 'border-ink-300 text-ink-600 dark:border-ink-700 dark:text-ink-300',
                    )}
                    style={selected ? { backgroundColor: tag.color } : undefined}
                  >
                    {tag.name}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="flex items-end justify-between gap-2 sm:col-span-2 lg:col-span-4">
            <Field label="Sort">
              <Select
                value={params.get('sort') ?? '-created_at'}
                onChange={(event) => update('sort', event.target.value)}
              >
                {SORTS.map((entry) => (
                  <option key={entry.value} value={entry.value}>
                    {entry.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Button variant="ghost" onClick={() => setParams(new URLSearchParams())}>
              Clear all
            </Button>
          </div>
        </Card>
      ) : null}

      {error ? <ErrorNote error={error} /> : null}
      {isLoading ? <Loading /> : null}

      {data && data.items.length === 0 ? (
        <EmptyState
          icon={<Boxes className="h-8 w-8" />}
          title="No item matches"
          hint="Change the filters, or add the item."
          action={
            <Link to="/items/new">
              <Button icon={<Plus className="h-4 w-4" />}>Add an item</Button>
            </Link>
          }
        />
      ) : null}

      {data && data.items.length > 0 ? (
        <div className={cx(isFetching && 'opacity-70 transition-opacity')}>
          {view === 'grid' ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {data.items.map((item) => (
                <ItemGridCard key={item.id} item={item} />
              ))}
            </div>
          ) : (
            <Card className="p-0">
              {data.items.map((item) => (
                <ItemRow key={item.id} item={item} />
              ))}
            </Card>
          )}

          {data.pages > 1 ? (
            <div className="mt-5 flex items-center justify-center gap-2">
              <Button
                variant="secondary"
                disabled={data.page <= 1}
                onClick={() => update('page', String(data.page - 1))}
              >
                Back
              </Button>
              <span className="text-sm text-ink-500">
                Page {data.page} of {data.pages}
              </span>
              <Button
                variant="secondary"
                disabled={data.page >= data.pages}
                onClick={() => update('page', String(data.page + 1))}
              >
                Next
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
