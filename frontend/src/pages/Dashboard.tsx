import {
  Boxes,
  Clock,
  HandHelping,
  Plus,
  Receipt,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { ItemRow } from '@/components/ItemCard'
import { Button, Card, EmptyState, ErrorNote, Loading, PageHeader } from '@/components/ui'
import { useItems } from '@/hooks/useItems'
import { useUpcomingMaintenance } from '@/hooks/useOperations'
import { useDashboard } from '@/hooks/useSystem'
import { formatDueIn, formatMoney } from '@/lib/format'

function Stat({
  label,
  value,
  icon,
  to,
  tone,
}: {
  label: string
  value: string | number
  icon: ReactNode
  to: string
  tone?: string
}) {
  return (
    <Link to={to} className="card p-4 transition-shadow hover:shadow-md">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-ink-500">{label}</span>
        <span className={tone ?? 'text-ink-400'}>{icon}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p>
    </Link>
  )
}

export default function Dashboard() {
  const summary = useDashboard()
  const recent = useItems({ sort: '-created_at', per_page: 5 })
  const due = useUpcomingMaintenance(30)

  if (summary.isLoading) return <Loading label="Reading your inventory" />
  if (summary.error) return <ErrorNote error={summary.error} />

  const data = summary.data
  if (!data) return null

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="What you own, where it is, and what needs attention."
        action={
          <Link to="/items/new">
            <Button icon={<Plus className="h-4 w-4" />}>Add an item</Button>
          </Link>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Items"
          value={data.total_items}
          icon={<Boxes className="h-4 w-4" />}
          to="/items"
        />
        <Stat
          label="Total value"
          value={formatMoney(data.total_value)}
          icon={<ShieldCheck className="h-4 w-4" />}
          to="/export"
        />
        <Stat
          label="Out on loan"
          value={data.lent_count}
          icon={<HandHelping className="h-4 w-4" />}
          to="/lending"
          tone={data.lent_count > 0 ? 'text-amber-500' : undefined}
        />
        <Stat
          label="Service due"
          value={data.maintenance_due_count}
          icon={<Wrench className="h-4 w-4" />}
          to="/maintenance"
          tone={data.maintenance_due_count > 0 ? 'text-amber-500' : undefined}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Recent additions</h2>
            <Link to="/items/new" className="text-sm text-accent-600 hover:underline dark:text-accent-400">
              Add an item
            </Link>
          </div>
          {recent.isLoading ? (
            <Loading />
          ) : (recent.data?.items.length ?? 0) === 0 ? (
            <EmptyState
              icon={<Boxes className="h-8 w-8" />}
              title="No items yet"
              hint="Add the first one, or photograph a shelf and let the AI list it."
              action={
                <Link to="/items/new">
                  <Button icon={<Plus className="h-4 w-4" />}>Add an item</Button>
                </Link>
              }
            />
          ) : (
            <div className="-mx-1">
              {recent.data?.items.map((item) => (
                <ItemRow key={item.id} item={item} />
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <h2 className="mb-3 text-sm font-semibold">Rooms by value</h2>
            {data.items_by_location.length === 0 ? (
              <p className="text-sm text-ink-500">No location holds an item yet.</p>
            ) : (
              <ul className="space-y-2">
                {data.items_by_location.slice(0, 6).map((row) => (
                  <li key={row.location_id} className="flex items-center justify-between text-sm">
                    <Link
                      to={`/items?location_id=${row.location_id}`}
                      className="truncate hover:underline"
                    >
                      {row.location_name}
                    </Link>
                    <span className="ml-2 shrink-0 text-ink-500">
                      {row.item_count} · {formatMoney(row.total_value)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Clock className="h-4 w-4 text-ink-400" /> Due in 30 days
            </h2>
            {(due.data?.length ?? 0) === 0 ? (
              <p className="text-sm text-ink-500">Nothing needs service.</p>
            ) : (
              <ul className="space-y-2">
                {due.data?.slice(0, 5).map((entry) => (
                  <li key={entry.id} className="text-sm">
                    <Link to={`/items/${entry.item_id}`} className="font-medium hover:underline">
                      {entry.item_name}
                    </Link>
                    <p className="text-xs text-ink-500">
                      {entry.description} · {formatDueIn(entry.days_until_due)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <Receipt className="h-4 w-4 text-ink-400" /> Receipts
            </h2>
            <p className="text-sm text-ink-500">
              {data.receipt_count} stored. {data.warranty_expiring_count} warranties end
              within 30 days.
            </p>
          </Card>
        </div>
      </div>
    </div>
  )
}
