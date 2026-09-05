/**
 * The AI helpers on the add page.
 *
 * The server has no GPU, so a scan can take tens of seconds. The upload route
 * returns a job at once, and this component follows it to the end.
 */

import { Camera, ScanBarcode, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { ai } from '@/api/endpoints'
import type { AiJob, BarcodeProduct, RecognizedItem } from '@/api/types'
import { useAiJob, useAiStatus } from '@/hooks/useSystem'
import { useBarcodeLookup } from '@/hooks/useItems'
import { cx } from '@/lib/format'
import { toastError } from '@/store/toast'
import { Button, Input, Modal, Spinner } from './ui'

export function AiPhotoButton({
  onResult,
  mode = 'recognize',
  label = 'Photograph an item',
}: {
  onResult: (items: RecognizedItem[], file: File) => void
  mode?: 'recognize' | 'bulk'
  label?: string
}) {
  const status = useAiStatus()
  const input = useRef<HTMLInputElement>(null)
  const [job, setJob] = useState<AiJob | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const followed = useAiJob(job)

  const off = status.data ? !status.data.enabled || !status.data.reachable : false

  const start = async (chosen: File) => {
    setBusy(true)
    setFile(chosen)
    try {
      const started = mode === 'bulk' ? await ai.bulkScan(chosen) : await ai.recognize(chosen)
      setJob(started)
    } catch (error) {
      toastError(error)
    } finally {
      setBusy(false)
    }
  }

  // The job finished. Hand the result up once, after the render.
  useEffect(() => {
    if (!followed.finished || !followed.job || !file) return
    const finished = followed.job
    setJob(null)
    setFile(null)
    if (finished.status === 'succeeded' && finished.recognize_result) {
      onResult(finished.recognize_result.items, file)
    } else {
      toastError(new Error(finished.error ?? 'The model returned nothing.'))
    }
    // `onResult` is a new function on every render of the parent, so it stays
    // out of the dependency list. The job identity is what matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [followed.finished, followed.job, file])

  return (
    <>
      <input
        ref={input}
        type="file"
        accept="image/*"
        hidden
        onChange={(event) => {
          const chosen = event.target.files?.[0]
          if (chosen) void start(chosen)
          event.target.value = ''
        }}
      />
      <Button
        type="button"
        variant="secondary"
        disabled={off}
        loading={busy}
        onClick={() => input.current?.click()}
        icon={<Sparkles className="h-4 w-4" />}
        title={off ? (status.data?.message ?? 'Ollama is not available.') : undefined}
      >
        {label}
      </Button>

      <Modal
        open={job !== null}
        title="The model is looking at the photograph"
        onClose={() => setJob(null)}
      >
        <div className="flex items-center gap-3 text-sm text-ink-600 dark:text-ink-300">
          <Spinner />
          <div>
            <p>This runs on the CPU, so it takes a while.</p>
            <p className="mt-1 text-ink-500">
              You may close this window. The scan keeps running.
            </p>
          </div>
        </div>
      </Modal>
    </>
  )
}

export function BarcodeButton({ onProduct }: { onProduct: (product: BarcodeProduct) => void }) {
  const lookup = useBarcodeLookup()
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')

  const submit = async () => {
    try {
      const product = await lookup.mutateAsync(code.trim())
      onProduct(product)
      setOpen(false)
      setCode('')
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <>
      <Button
        type="button"
        variant="secondary"
        onClick={() => setOpen(true)}
        icon={<ScanBarcode className="h-4 w-4" />}
      >
        Barcode
      </Button>

      <Modal
        open={open}
        title="Look up a barcode"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void submit()} loading={lookup.isPending}>
              Look it up
            </Button>
          </>
        }
      >
        <p className="mb-3 text-sm text-ink-500">
          Type the number under the barcode. HomeStock asks Open Food Facts and
          UPCitemdb, and fills the form with what they know.
        </p>
        <Input
          autoFocus
          inputMode="numeric"
          placeholder="9300650001234"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') void submit()
          }}
        />
      </Modal>
    </>
  )
}

export function SuggestionList({
  suggestions,
  selected,
  onToggle,
}: {
  suggestions: RecognizedItem[]
  selected: number[]
  onToggle: (index: number) => void
}) {
  return (
    <ul className="space-y-2">
      {suggestions.map((entry, index) => {
        const active = selected.includes(index)
        return (
          <li key={`${entry.name}-${index}`}>
            <button
              type="button"
              onClick={() => onToggle(index)}
              className={cx(
                'flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                active
                  ? 'border-accent-500 bg-accent-50 dark:bg-accent-500/10'
                  : 'border-ink-200 hover:bg-ink-100 dark:border-ink-800 dark:hover:bg-ink-800',
              )}
            >
              <Camera className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{entry.name}</p>
                <p className="text-xs text-ink-500">
                  {[entry.brand, entry.category, entry.condition].filter(Boolean).join(' · ') ||
                    'No other detail'}
                </p>
              </div>
              {entry.estimated_value_aud ? (
                <span className="text-sm">${entry.estimated_value_aud}</span>
              ) : null}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
