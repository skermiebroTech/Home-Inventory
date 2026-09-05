import { FileSpreadsheet, FileText, Package } from 'lucide-react'
import type { ReactNode } from 'react'
import { useState } from 'react'

import { exports } from '@/api/endpoints'
import { Button, Card, Input, PageHeader } from '@/components/ui'
import { useDashboard } from '@/hooks/useSystem'
import { formatMoney } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'

function Choice({
  icon,
  title,
  text,
  action,
}: {
  icon: ReactNode
  title: string
  text: string
  action: ReactNode
}) {
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-accent-600 dark:text-accent-400">
        {icon}
        <h2 className="text-sm font-semibold text-ink-900 dark:text-ink-100">{title}</h2>
      </div>
      <p className="flex-1 text-sm text-ink-500">{text}</p>
      {action}
    </Card>
  )
}

export default function Export() {
  const summary = useDashboard()
  const [busy, setBusy] = useState<string | null>(null)
  const [minValue, setMinValue] = useState('')
  const [withPhotos, setWithPhotos] = useState(true)

  const run = async (name: string, work: () => Promise<void>) => {
    setBusy(name)
    try {
      await work()
      toastOk('The download started.')
    } catch (error) {
      toastError(error)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <PageHeader
        title="Export"
        subtitle={
          summary.data
            ? `${summary.data.total_items} items worth ${formatMoney(summary.data.total_value)}.`
            : 'Take your data with you.'
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Choice
          icon={<FileSpreadsheet className="h-5 w-5" />}
          title="CSV"
          text="Every item as one row. A spreadsheet opens it."
          action={
            <Button
              variant="secondary"
              loading={busy === 'csv'}
              onClick={() => void run('csv', exports.csv)}
            >
              Download the CSV
            </Button>
          }
        />

        <Choice
          icon={<Package className="h-5 w-5" />}
          title="Full backup"
          text="A ZIP with the database, every photograph, the CSV, and a metadata file."
          action={
            <Button
              variant="secondary"
              loading={busy === 'full'}
              onClick={() => void run('full', exports.full)}
            >
              Download the ZIP
            </Button>
          }
        />

        <Choice
          icon={<FileText className="h-5 w-5" />}
          title="Insurance report"
          text="A PDF with the values, grouped by category, with a photograph beside each item."
          action={
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={withPhotos}
                  onChange={(event) => setWithPhotos(event.target.checked)}
                  className="h-4 w-4 rounded border-ink-300"
                />
                Include the photographs
              </label>
              <Input
                inputMode="decimal"
                placeholder="Only items over this value"
                value={minValue}
                onChange={(event) => setMinValue(event.target.value)}
              />
              <Button
                variant="secondary"
                loading={busy === 'pdf'}
                onClick={() =>
                  void run('pdf', () =>
                    exports.insurance({
                      include_photos: withPhotos,
                      min_value: minValue ? Number(minValue) : undefined,
                    }),
                  )
                }
                className="w-full"
              >
                Build the PDF
              </Button>
            </div>
          }
        />
      </div>
    </div>
  )
}
