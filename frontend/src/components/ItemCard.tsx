/** One item in the grid, and one item in the list. */

import { Boxes, HandHelping } from 'lucide-react'
import { Link } from 'react-router-dom'

import { mediaUrl } from '@/api/client'
import type { Item } from '@/api/types'
import { formatMoney } from '@/lib/format'
import { TagList } from './pickers'
import { Badge } from './ui'

function Thumb({ item, className }: { item: Item; className: string }) {
  const source = mediaUrl(item.primary_photo?.thumbnail_path ?? item.primary_photo?.file_path)
  if (!source) {
    return (
      <div className={`${className} flex items-center justify-center bg-ink-100 dark:bg-ink-800`}>
        <Boxes className="h-6 w-6 text-ink-400" />
      </div>
    )
  }
  return <img src={source} alt="" loading="lazy" className={`${className} object-cover`} />
}

export function ItemGridCard({ item }: { item: Item }) {
  return (
    <Link
      to={`/items/${item.id}`}
      className="card group overflow-hidden transition-shadow hover:shadow-md"
    >
      <Thumb item={item} className="aspect-square w-full" />
      <div className="space-y-1 p-3">
        <p className="truncate text-sm font-medium">{item.name}</p>
        <p className="text-xs text-ink-500">
          {item.brand ?? item.category ?? 'No category'}
        </p>
        <div className="flex items-center justify-between pt-1">
          <span className="text-sm font-medium">
            {formatMoney(item.current_value ?? item.purchase_price)}
          </span>
          {item.quantity > 1 ? <Badge>{item.quantity}×</Badge> : null}
        </div>
        {item.is_lent ? (
          <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
            <HandHelping className="mr-1 h-3 w-3" /> {item.lent_to}
          </Badge>
        ) : null}
      </div>
    </Link>
  )
}

export function ItemRow({ item }: { item: Item }) {
  return (
    <Link
      to={`/items/${item.id}`}
      className="flex items-center gap-3 border-b border-ink-200 px-3 py-2.5 last:border-0 hover:bg-ink-100/70 dark:border-ink-800 dark:hover:bg-ink-800/50"
    >
      <Thumb item={item} className="h-11 w-11 shrink-0 rounded-lg" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{item.name}</p>
        <p className="truncate text-xs text-ink-500">
          {[item.brand, item.category].filter(Boolean).join(' · ') || 'No category'}
        </p>
      </div>
      <div className="hidden sm:block">
        <TagList tags={item.tags.slice(0, 3)} />
      </div>
      {item.is_lent ? (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          Lent
        </Badge>
      ) : null}
      <span className="w-24 text-right text-sm">
        {formatMoney(item.current_value ?? item.purchase_price)}
      </span>
    </Link>
  )
}
