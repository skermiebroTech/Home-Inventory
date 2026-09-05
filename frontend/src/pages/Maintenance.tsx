import { CalendarClock, Wrench } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Card, EmptyState, Loading, PageHeader, Select } from '@/components/ui'
import { useUpcomingMaintenance } from '@/hooks/useOperations'
import { cx, formatDate, formatDueIn, formatMoney } from '@/lib/format'

export default function Maintenance() {
  const [days, setDays] = useState(30)
  const { data, isLoading } = useUpcomingMaintenance(days)

  const overdue = (data ?? []).filter((entry) => entry.days_until_due < 0)
  const soon = (data ?? []).filter((entry) => entry.days_until_due >= 0)

  return (
    <div>
      <PageHeader
        title="Maintenance"
        subtitle="Work that is due, and work that is late."
        action={
          <Select
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
            aria-label="How far ahead to look"
            className="w-40"
          >
            <option value={7}>Next 7 days</option>
            <option value={30}>Next 30 days</option>
            <option value={90}>Next 90 days</option>
            <option value={365}>Next year</option>
          </Select>
        }
      />

      {isLoading ? <Loading /> : null}

      {data && data.length === 0 ? (
        <EmptyState
          icon={<Wrench className="h-8 w-8" />}
          title="Nothing is due"
          hint="Open an item and record service work to set the next date."
        />
      ) : null}

      {overdue.length > 0 ? (
        <section className="mb-5">
          <h2 className="mb-2 text-sm font-semibold text-red-600 dark:text-red-400">Late</h2>
          <Card className="p-0">
            {overdue.map((entry) => (
              <Row key={entry.id} entry={entry} late />
            ))}
          </Card>
        </section>
      ) : null}

      {soon.length > 0 ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Coming up</h2>
          <Card className="p-0">
            {soon.map((entry) => (
              <Row key={entry.id} entry={entry} />
            ))}
          </Card>
        </section>
      ) : null}
    </div>
  )
}

function Row({
  entry,
  late,
}: {
  entry: {
    id: string
    item_id: string
    item_name: string
    description: string
    next_due_date: string | null
    days_until_due: number
    cost: string | null
  }
  late?: boolean
}) {
  return (
    <Link
      to={`/items/${entry.item_id}`}
      className="flex items-center gap-3 border-b border-ink-200 px-4 py-3 last:border-0 hover:bg-ink-100/70 dark:border-ink-800 dark:hover:bg-ink-800/50"
    >
      <CalendarClock
        className={cx('h-5 w-5 shrink-0', late ? 'text-red-500' : 'text-ink-400')}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{entry.item_name}</p>
        <p className="truncate text-xs text-ink-500">{entry.description}</p>
      </div>
      <div className="text-right">
        <p className={cx('text-sm', late && 'font-medium text-red-600 dark:text-red-400')}>
          {formatDueIn(entry.days_until_due)}
        </p>
        <p className="text-xs text-ink-500">
          {formatDate(entry.next_due_date)}
          {entry.cost ? ` · ${formatMoney(entry.cost)}` : ''}
        </p>
      </div>
    </Link>
  )
}
