/** The operator page: the backups, the AI, the server health, and the account. */

import {
  AlertTriangle,
  CheckCircle2,
  Database,
  HardDrive,
  Play,
  Save,
  Sparkles,
  Upload,
  XCircle,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { system } from '@/api/endpoints'
import type { BackupSchedule } from '@/api/types'
import {
  Button,
  Card,
  Field,
  Input,
  Loading,
  PageHeader,
  Select,
} from '@/components/ui'
import { useAiStatus, useBackupStatus, useHealth, useRunBackup, useSetSchedule } from '@/hooks/useSystem'
import { formatBytes, formatDateTime } from '@/lib/format'
import { useAuthStore } from '@/store/auth'
import { toastError, toastOk } from '@/store/toast'

const CRONS = [
  { value: '0 3 * * *', label: 'Every night at 3 am' },
  { value: '0 3 * * 0', label: 'Every Sunday at 3 am' },
  { value: '0 3 1 * *', label: 'The first of the month at 3 am' },
  { value: '0 */6 * * *', label: 'Every six hours' },
]

function Dot({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
  ) : (
    <XCircle className="h-4 w-4 text-red-500" />
  )
}

export default function Settings() {
  const user = useAuthStore((state) => state.user)
  const health = useHealth(true)
  const aiStatus = useAiStatus()
  const backup = useBackupStatus()
  const setSchedule = useSetSchedule()
  const runBackup = useRunBackup()
  const restoreInput = useRef<HTMLInputElement>(null)
  const [restoring, setRestoring] = useState(false)

  const [schedule, setLocalSchedule] = useState<BackupSchedule>({
    enabled: false,
    cron: '0 3 * * *',
    retention: 7,
    rclone_remote: '',
  })

  useEffect(() => {
    if (backup.data) setLocalSchedule(backup.data.schedule)
  }, [backup.data])

  const save = async () => {
    try {
      await setSchedule.mutateAsync(schedule)
      toastOk('The schedule is saved.')
    } catch (error) {
      toastError(error)
    }
  }

  const restore = async (file: File | undefined) => {
    if (!file) return
    const sure = window.confirm(
      'A restore replaces every row and every file. Continue?',
    )
    if (!sure) return
    setRestoring(true)
    try {
      const result = await system.restore(file)
      toastOk(result.message)
    } catch (error) {
      toastError(error)
    } finally {
      setRestoring(false)
    }
  }

  if (health.isLoading) return <Loading />

  return (
    <div className="space-y-4">
      <PageHeader title="Settings" subtitle={`Signed in as ${user?.email ?? ''}`} />

      {health.data?.secret_key_is_default ? (
        <div className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">HS_SECRET_KEY still holds the default value.</p>
            <p>
              Generate one with <code>openssl rand -hex 32</code>, put it in the
              container settings, and restart.
            </p>
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Database className="h-4 w-4 text-ink-400" /> Server
          </h2>
          <dl className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-ink-500">Status</dt>
              <dd className="font-medium">{health.data?.status}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-ink-500">Version</dt>
              <dd>{health.data?.version}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-ink-500">Database</dt>
              <dd className="flex items-center gap-1">
                <Dot ok={health.data?.database.ok ?? false} />
                {health.data?.database.latency_ms
                  ? `${health.data.database.latency_ms} ms`
                  : (health.data?.database.detail ?? '')}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-ink-500">Ollama</dt>
              <dd className="flex items-center gap-1">
                <Dot ok={health.data?.ollama.ok ?? false} />
                {health.data?.ollama.ok ? 'reachable' : 'not reachable'}
              </dd>
            </div>
            {health.data?.disk ? (
              <div>
                <div className="flex items-center justify-between">
                  <dt className="flex items-center gap-1 text-ink-500">
                    <HardDrive className="h-3.5 w-3.5" /> Disk
                  </dt>
                  <dd>
                    {formatBytes(health.data.disk.free_bytes)} free of{' '}
                    {formatBytes(health.data.disk.total_bytes)}
                  </dd>
                </div>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-ink-200 dark:bg-ink-800">
                  <div
                    className="h-full rounded-full bg-accent-500"
                    style={{ width: `${health.data.disk.percent_used}%` }}
                  />
                </div>
              </div>
            ) : null}
          </dl>
        </Card>

        <Card>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="h-4 w-4 text-ink-400" /> AI
          </h2>
          {aiStatus.isLoading ? (
            <Loading label="Asking Ollama" />
          ) : (
            <dl className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-ink-500">Turned on</dt>
                <dd>
                  <Dot ok={aiStatus.data?.enabled ?? false} />
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-500">Reachable</dt>
                <dd>
                  <Dot ok={aiStatus.data?.reachable ?? false} />
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-500">Address</dt>
                <dd className="truncate">{aiStatus.data?.base_url}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-500">Vision model</dt>
                <dd className="flex items-center gap-1">
                  <Dot ok={aiStatus.data?.vision_model_installed ?? false} />
                  {aiStatus.data?.vision_model}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-500">Text model</dt>
                <dd className="flex items-center gap-1">
                  <Dot ok={aiStatus.data?.text_model_installed ?? false} />
                  {aiStatus.data?.text_model}
                </dd>
              </div>
              {aiStatus.data?.message ? (
                <p className="pt-1 text-xs text-ink-500">{aiStatus.data.message}</p>
              ) : null}
              <p className="pt-1 text-xs text-ink-500">
                Every model runs on the CPU. A scan that takes longer than{' '}
                {aiStatus.data?.inline_timeout_seconds ?? 8} seconds becomes a job
                that the page follows.
              </p>
            </dl>
          )}
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 text-sm font-semibold">Automatic backup</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Run it">
            <Select
              value={schedule.enabled ? 'on' : 'off'}
              onChange={(event) =>
                setLocalSchedule({ ...schedule, enabled: event.target.value === 'on' })
              }
            >
              <option value="off">Off</option>
              <option value="on">On</option>
            </Select>
          </Field>
          <Field label="When">
            <Select
              value={schedule.cron}
              onChange={(event) => setLocalSchedule({ ...schedule, cron: event.target.value })}
            >
              {CRONS.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.label}
                </option>
              ))}
              {CRONS.every((entry) => entry.value !== schedule.cron) ? (
                <option value={schedule.cron}>{schedule.cron}</option>
              ) : null}
            </Select>
          </Field>
          <Field label="Keep">
            <Input
              type="number"
              min={1}
              max={365}
              value={schedule.retention}
              onChange={(event) =>
                setLocalSchedule({ ...schedule, retention: Number(event.target.value) })
              }
            />
          </Field>
          <Field label="rclone remote" hint="For example b2:my-bucket/homestock">
            <Input
              value={schedule.rclone_remote ?? ''}
              onChange={(event) =>
                setLocalSchedule({ ...schedule, rclone_remote: event.target.value })
              }
            />
          </Field>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => void save()} loading={setSchedule.isPending} icon={<Save className="h-4 w-4" />}>
            Save the schedule
          </Button>
          <Button
            variant="secondary"
            loading={runBackup.isPending}
            icon={<Play className="h-4 w-4" />}
            onClick={async () => {
              try {
                const result = await runBackup.mutateAsync()
                toastOk(result.message)
              } catch (error) {
                toastError(error)
              }
            }}
          >
            Run one now
          </Button>
          <input
            ref={restoreInput}
            type="file"
            accept=".zip,application/zip"
            hidden
            onChange={(event) => {
              void restore(event.target.files?.[0])
              event.target.value = ''
            }}
          />
          <Button
            variant="secondary"
            loading={restoring}
            icon={<Upload className="h-4 w-4" />}
            onClick={() => restoreInput.current?.click()}
            disabled={user?.role !== 'admin'}
            title={user?.role !== 'admin' ? 'Only the owner account may restore.' : undefined}
          >
            Restore from a ZIP
          </Button>
        </div>

        {backup.data ? (
          <div className="mt-4 border-t border-ink-200 pt-3 text-sm dark:border-ink-800">
            <p className="text-ink-500">
              Next run: {formatDateTime(backup.data.next_run_at)} · Last run:{' '}
              {formatDateTime(backup.data.last_run_at)}
              {backup.data.last_run_ok === false ? ' (it failed)' : ''}
            </p>
            {backup.data.last_run_error ? (
              <p className="mt-1 text-red-600 dark:text-red-400">{backup.data.last_run_error}</p>
            ) : null}
            {backup.data.backups.length > 0 ? (
              <ul className="mt-2 space-y-1">
                {backup.data.backups.slice(0, 5).map((file) => (
                  <li key={file.filename} className="flex justify-between text-xs text-ink-500">
                    <span className="truncate font-mono">{file.filename}</span>
                    <span>{formatBytes(file.size_bytes)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-xs text-ink-500">No archive on disk yet.</p>
            )}
          </div>
        ) : null}
      </Card>
    </div>
  )
}
