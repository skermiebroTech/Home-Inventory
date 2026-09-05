/**
 * The first run wizard.
 *
 * Step 1 makes the owner account, because the server reports
 * `setup_required` while no account exists. Step 2 builds the first rooms.
 * Step 3 reports whether the AI features can work, and lets the operator go
 * on without them.
 */

import { AlertTriangle, Boxes, Check, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useQueryClient } from '@tanstack/react-query'

import { Button, Card, ErrorNote, Field, Input, Spinner } from '@/components/ui'
import { useCreateLocation } from '@/hooks/useCatalogue'
import { useAiStatus, useHealth } from '@/hooks/useSystem'
import { cx } from '@/lib/format'
import { useAuthStore } from '@/store/auth'
import { toastError } from '@/store/toast'

const SUGGESTED_ROOMS = ['Kitchen', 'Garage', 'Living room', 'Main bedroom', 'Shed', 'Office']

export default function Setup() {
  const navigate = useNavigate()
  const health = useHealth()
  const register = useAuthStore((state) => state.register)
  const accessToken = useAuthStore((state) => state.accessToken)
  const createLocation = useCreateLocation()
  const queryClient = useQueryClient()

  const [step, setStep] = useState(accessToken ? 2 : 1)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [home, setHome] = useState('Home')
  const [rooms, setRooms] = useState<string[]>(['Kitchen', 'Garage'])
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const createAccount = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register(email, name, password)
      // The health check reported `setup_required`. It is stale now.
      await queryClient.invalidateQueries({ queryKey: ['health'] })
      setStep(2)
    } catch (failure) {
      setError(failure)
    } finally {
      setBusy(false)
    }
  }

  const createRooms = async () => {
    setBusy(true)
    try {
      const root = await createLocation.mutateAsync({ name: home.trim() || 'Home', type: 'room' })
      for (const room of rooms) {
        await createLocation.mutateAsync({ name: room, type: 'zone', parent_id: root.id })
      }
      setStep(3)
    } catch (failure) {
      toastError(failure)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-full max-w-lg flex-col justify-center p-4">
      <div className="mb-6 flex items-center gap-2">
        <Boxes className="h-7 w-7 text-accent-600" />
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Set up HomeStock</h1>
          <p className="text-sm text-ink-500">Three short steps.</p>
        </div>
      </div>

      <ol className="mb-5 flex gap-2 text-xs">
        {['Account', 'Rooms', 'AI'].map((label, index) => (
          <li
            key={label}
            className={cx(
              'flex-1 rounded-lg border px-2 py-1.5 text-center',
              step > index + 1
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300'
                : step === index + 1
                  ? 'border-accent-400 bg-accent-50 font-medium text-accent-700 dark:border-accent-400/40 dark:bg-accent-500/10 dark:text-accent-400'
                  : 'border-ink-200 text-ink-500 dark:border-ink-800',
            )}
          >
            {step > index + 1 ? <Check className="mx-auto h-3.5 w-3.5" /> : label}
          </li>
        ))}
      </ol>

      {health.data?.secret_key_is_default ? (
        <div className="mb-4 flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">HS_SECRET_KEY still holds the default value.</p>
            <p className="mt-1">
              Every sign in token is signed with it. Generate one and restart the
              container:
            </p>
            <code className="mt-1 block rounded bg-amber-100 px-2 py-1 font-mono text-xs dark:bg-amber-900/60">
              openssl rand -hex 32
            </code>
          </div>
        </div>
      ) : null}

      {step === 1 ? (
        <Card>
          <h2 className="mb-1 text-sm font-semibold">Create the owner account</h2>
          <p className="mb-4 text-sm text-ink-500">
            The first account owns this installation. It may restore a backup.
          </p>
          <form onSubmit={createAccount} className="space-y-4">
            <Field label="Your name">
              <Input required value={name} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Field label="Email">
              <Input
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            <Field label="Password" hint="Eight characters or more.">
              <Input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>
            {error ? <ErrorNote error={error} /> : null}
            <Button type="submit" loading={busy} className="w-full">
              Create the account
            </Button>
          </form>
        </Card>
      ) : null}

      {step === 2 ? (
        <Card>
          <h2 className="mb-1 text-sm font-semibold">Add the first rooms</h2>
          <p className="mb-4 text-sm text-ink-500">
            A location holds items. Rooms sit under one home, and containers sit
            under a room. You can change all of this later.
          </p>
          <Field label="Home name">
            <Input value={home} onChange={(event) => setHome(event.target.value)} />
          </Field>
          <p className="label mt-4">Rooms</p>
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTED_ROOMS.map((room) => {
              const active = rooms.includes(room)
              return (
                <button
                  key={room}
                  type="button"
                  onClick={() =>
                    setRooms(active ? rooms.filter((r) => r !== room) : [...rooms, room])
                  }
                  className={cx(
                    'rounded-full border px-3 py-1 text-xs',
                    active
                      ? 'border-accent-500 bg-accent-50 text-accent-700 dark:bg-accent-500/10 dark:text-accent-400'
                      : 'border-ink-300 text-ink-600 dark:border-ink-700 dark:text-ink-300',
                  )}
                >
                  {room}
                </button>
              )
            })}
          </div>
          <div className="mt-5 flex justify-between">
            <Button variant="ghost" onClick={() => setStep(3)}>
              Skip
            </Button>
            <Button onClick={() => void createRooms()} loading={busy}>
              Create {rooms.length + 1} locations
            </Button>
          </div>
        </Card>
      ) : null}

      {step === 3 ? <AiStep onDone={() => navigate('/')} /> : null}
    </div>
  )
}

function AiStep({ onDone }: { onDone: () => void }) {
  const status = useAiStatus()

  return (
    <Card>
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="h-4 w-4 text-accent-600" /> The AI features
      </h2>
      <p className="mb-4 text-sm text-ink-500">
        HomeStock reads a photograph and fills the form. Ollama does that work
        on your own server. The rest of HomeStock works without it.
      </p>

      {status.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-ink-500">
          <Spinner /> Asking Ollama
        </div>
      ) : status.data?.reachable ? (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">
          <p className="font-medium">Ollama answers at {status.data.base_url}.</p>
          <p className="mt-1">
            {status.data.vision_model_installed
              ? `The model ${status.data.vision_model} is installed.`
              : `Pull the model first: ollama pull ${status.data.vision_model}`}
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-ink-300 bg-ink-100 p-3 text-sm dark:border-ink-700 dark:bg-ink-800">
          <p className="font-medium">Ollama does not answer.</p>
          <p className="mt-1 text-ink-600 dark:text-ink-300">
            {status.data?.message ?? 'Set HS_OLLAMA_URL, or leave the AI features off.'}
          </p>
        </div>
      )}

      <Button className="mt-5 w-full" onClick={onDone}>
        Open HomeStock
      </Button>
    </Card>
  )
}
