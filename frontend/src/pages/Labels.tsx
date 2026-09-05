/** Print QR labels for items or for locations. */

import { Printer, QrCode } from 'lucide-react'
import { useState } from 'react'

import QrImage from '@/components/QrImage'
import { Button, Card, EmptyState, Loading, PageHeader, Select } from '@/components/ui'
import { flattenTree, useLocationTree } from '@/hooks/useCatalogue'
import { useItems } from '@/hooks/useItems'
import { cx } from '@/lib/format'

type Kind = 'items' | 'locations'

export default function Labels() {
  const [kind, setKind] = useState<Kind>('items')
  const [selected, setSelected] = useState<string[]>([])
  const items = useItems({ per_page: 200, sort: 'name' })
  const tree = useLocationTree()

  const rows =
    kind === 'items'
      ? (items.data?.items ?? []).map((item) => ({
          id: item.id,
          name: item.name,
          tag: item.asset_tag,
        }))
      : flattenTree(tree.data ?? []).map((row) => ({
          id: row.id,
          name: row.label,
          tag: null,
        }))

  const toggle = (id: string) =>
    setSelected((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id],
    )

  const chosen = rows.filter((row) => selected.includes(row.id))

  return (
    <div>
      <PageHeader
        title="Labels"
        subtitle="A QR label opens the record when a phone camera reads it."
        action={
          <div className="flex gap-2">
            <Select
              value={kind}
              onChange={(event) => {
                setKind(event.target.value as Kind)
                setSelected([])
              }}
              className="w-36"
              aria-label="What to label"
            >
              <option value="items">Items</option>
              <option value="locations">Locations</option>
            </Select>
            <Button
              onClick={() => window.print()}
              disabled={chosen.length === 0}
              icon={<Printer className="h-4 w-4" />}
            >
              Print {chosen.length || ''}
            </Button>
          </div>
        }
      />

      {items.isLoading || tree.isLoading ? <Loading /> : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="print:hidden lg:col-span-1">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Choose</h2>
            <button
              className="text-xs text-accent-600 hover:underline dark:text-accent-400"
              onClick={() =>
                setSelected(selected.length === rows.length ? [] : rows.map((row) => row.id))
              }
            >
              {selected.length === rows.length ? 'None' : 'All'}
            </button>
          </div>
          <ul className="max-h-[28rem] space-y-0.5 overflow-y-auto">
            {rows.map((row) => (
              <li key={row.id}>
                <label className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-ink-100 dark:hover:bg-ink-800">
                  <input
                    type="checkbox"
                    checked={selected.includes(row.id)}
                    onChange={() => toggle(row.id)}
                    className="h-4 w-4 rounded border-ink-300"
                  />
                  <span className="truncate">
                    {row.tag ? (
                      <span className="mr-2 font-mono text-xs text-ink-500">
                        {row.tag}
                      </span>
                    ) : null}
                    {row.name}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </Card>

        <div className="lg:col-span-2">
          {chosen.length === 0 ? (
            <EmptyState
              icon={<QrCode className="h-8 w-8" />}
              title="Nothing chosen"
              hint="Tick the items or the locations that need a label."
            />
          ) : (
            <div
              className={cx(
                'grid grid-cols-2 gap-3 sm:grid-cols-3',
                'print:grid-cols-3 print:gap-2',
              )}
            >
              {chosen.map((row) => (
                <figure
                  key={row.id}
                  className="card flex flex-col items-center gap-2 p-3 print:border print:shadow-none"
                >
                  <QrImage
                    path={`/api/${kind}/${row.id}/qr?size=240`}
                    alt={`QR code for ${row.name}`}
                    className="w-full"
                  />
                  <figcaption className="w-full text-center text-xs">
                    {row.tag ? (
                      <span className="block font-mono text-sm">{row.tag}</span>
                    ) : null}
                    <span className="block truncate">{row.name}</span>
                  </figcaption>
                </figure>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
