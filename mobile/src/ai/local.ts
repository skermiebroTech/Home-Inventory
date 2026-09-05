/**
 * Recognition on the phone itself.
 *
 * The server has no GPU and its processors are from 2012, so a photograph
 * costs it tens of seconds. The phone holds a better processor than that, and
 * it holds the photograph already. This runs a small vision model on the
 * phone, with no network at all.
 *
 * The weights are not in the application. They are one download of half a
 * gigabyte or more, which the person starts and can undo.
 */

import AsyncStorage from '@react-native-async-storage/async-storage'
import * as FileSystem from 'expo-file-system'

import { api, serverUrl } from '@/api/client'
import { initLlama, type LlamaContext } from 'llama.rn'

import type { RecognizedItem } from '@/api/types'

/** Where the weights live. The cache directory would be swept by Android. */
const HOME = `${FileSystem.documentDirectory}models/`

export interface ModelFile {
  url: string
  /** The size that the host reports. It makes the bar honest at once. */
  bytes: number
}

export interface LocalModel {
  id: string
  name: string
  note: string
  /** The weights, and the part that reads a picture. */
  model: ModelFile
  mmproj: ModelFile
  /** Tokens that one picture may cost. It bounds the time per photograph. */
  imageTokens: number
}

/** What the whole download costs, in bytes. */
export function totalBytes(model: LocalModel): number {
  return model.model.bytes + model.mmproj.bytes
}

export const MODELS: LocalModel[] = [
  {
    id: 'smolvlm2-2.2b',
    name: 'SmolVLM2 2.2B',
    note: 'Slower, and it names things better.',
    model: {
      url: 'https://huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF/resolve/main/SmolVLM2-2.2B-Instruct-Q4_K_M.gguf',
      bytes: 1_112_602_656,
    },
    mmproj: {
      url: 'https://huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF/resolve/main/mmproj-SmolVLM2-2.2B-Instruct-Q8_0.gguf',
      bytes: 592_523_200,
    },
    imageTokens: 900,
  },
  {
    id: 'smolvlm2-500m',
    name: 'SmolVLM2 500M',
    note: 'Quick, and it misses detail.',
    model: {
      url: 'https://huggingface.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main/SmolVLM2-500M-Video-Instruct-Q8_0.gguf',
      bytes: 436_808_704,
    },
    mmproj: {
      url: 'https://huggingface.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main/mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf',
      bytes: 108_785_184,
    },
    imageTokens: 600,
  },
]

/**
 * The words that the server sends, so both answers have the same shape.
 *
 * The application cannot ask the server for them: the point of this file is
 * that there is no server.
 */
const PROMPT =
  'You are a home inventory assistant. Analyze this image and identify ' +
  'every distinct item visible. For each item return a JSON array of ' +
  'objects with: name, brand (if visible, else null), category, subcategory, ' +
  'estimated_value_aud (number), condition (new/good/fair/poor). Be ' +
  "specific — say 'DeWalt DCD771 cordless drill' not just 'drill'."

export interface LocalStatus {
  /** Both files are on the phone. */
  ready: boolean
  /** How much of the download is here, in bytes. */
  bytes: number
}

function pathOf(model: LocalModel, part: 'model' | 'mmproj'): string {
  return `${HOME}${model.id}-${part}.gguf`
}

/** One model, as the server describes what it holds. */
export interface ServerModel {
  id: string
  ready: boolean
  cached_bytes: number
  bytes: number
  fetching: boolean
  files: Array<{ part: string; path: string }>
}

/**
 * Ask the server which models it keeps.
 *
 * A copy on the server comes down the local network in a minute, where the
 * public host took an hour. An empty answer is not a failure: the phone then
 * fetches from the internet as before.
 */
export async function serverModels(): Promise<ServerModel[]> {
  try {
    return await api.get<ServerModel[]>('/api/models')
  } catch {
    return []
  }
}

/** Ask the server to keep this model, so every phone downloads it locally. */
export async function askServerToCache(model: LocalModel): Promise<void> {
  await api.post(`/api/models/${model.id}/fetch`, {})
}

/**
 * Where each file should come from.
 *
 * The server wins when it holds the whole model. Anything else and the phone
 * goes to the public host, because half a file is worse than a slow one.
 */
function sourceOf(
  model: LocalModel,
  part: 'model' | 'mmproj',
  onServer: ServerModel | undefined,
): string {
  const file = onServer?.ready
    ? onServer.files.find((one) => one.part === part)
    : undefined
  return file ? `${serverUrl()}${file.path}` : model[part].url
}

async function sizeOf(path: string): Promise<number> {
  const info = await FileSystem.getInfoAsync(path)
  return info.exists && !info.isDirectory ? (info.size ?? 0) : 0
}

export async function statusOf(model: LocalModel): Promise<LocalStatus> {
  const [weights, projector] = await Promise.all([
    sizeOf(pathOf(model, 'model')),
    sizeOf(pathOf(model, 'mmproj')),
  ])
  return { ready: weights > 0 && projector > 0, bytes: weights + projector }
}

/** What the screen shows while the weights arrive. */
export interface DownloadProgress {
  /** Between 0 and 1, across both files together. */
  fraction: number
  /** Bytes on the phone so far, and bytes in total. */
  written: number
  total: number
  /** The recent rate, in bytes each second. Zero until it is known. */
  perSecond: number
  /** Seconds left at that rate, or null while it is unknown. */
  secondsLeft: number | null
}

/** The caller stopped the download. Not a failure, so not an alarm. */
export class DownloadCancelled extends Error {
  constructor() {
    super('The download was cancelled.')
    this.name = 'DownloadCancelled'
  }
}

/**
 * Where an unfinished download left off.
 *
 * Android may stop the application while a download of two gigabytes runs.
 * The bytes already on disk stay, and this holds the token that lets the
 * next start carry on from them instead of beginning again.
 */
const RESUME_KEY = 'homestock.download'

interface ResumeState {
  modelId: string
  part: 'model' | 'mmproj'
  resumeData?: string
}

async function saveResume(state: ResumeState | null): Promise<void> {
  if (state) await AsyncStorage.setItem(RESUME_KEY, JSON.stringify(state))
  else await AsyncStorage.removeItem(RESUME_KEY)
}

/** The model whose download stopped part way, if there is one. */
export async function unfinished(): Promise<LocalModel | null> {
  try {
    const raw = await AsyncStorage.getItem(RESUME_KEY)
    if (!raw) return null
    const state = JSON.parse(raw) as ResumeState
    return MODELS.find((model) => model.id === state.modelId) ?? null
  } catch {
    return null
  }
}

let task: FileSystem.DownloadResumable | null = null
let stopped = false

/** Stop the download and throw away the part that arrived. */
export async function cancel(): Promise<void> {
  stopped = true
  const running = task
  task = null
  try {
    await running?.cancelAsync()
  } catch {
    // The task may have ended between the tap and here.
  }
  await saveResume(null)
}

/**
 * Fetch the weights.
 *
 * The two files are one download to the person watching, so the numbers add
 * up across both. The rate is smoothed: a raw reading jumps about, and a
 * figure that flickers tells nobody anything.
 *
 * A download that stops carries on from the bytes already written, whether
 * it stopped because the application closed or because somebody cancelled
 * and started again.
 */
export async function download(
  model: LocalModel,
  onProgress: (progress: DownloadProgress) => void,
): Promise<void> {
  await FileSystem.makeDirectoryAsync(HOME, { intermediates: true }).catch(
    () => undefined,
  )
  stopped = false

  // The server may hold the same weights on the local network.
  const onServer = (await serverModels()).find((one) => one.id === model.id)

  const parts: Array<'model' | 'mmproj'> = ['model', 'mmproj']
  const total = totalBytes(model)
  const done: Record<string, number> = {}

  // The files that are already here count as written.
  for (const part of parts) {
    const have = await sizeOf(pathOf(model, part))
    if (have > 0) done[part] = have
  }

  let rate = 0
  let lastAt = Date.now()
  let lastBytes = Object.values(done).reduce((sum, value) => sum + value, 0)

  const report = (): void => {
    const written = parts.reduce((sum, key) => sum + (done[key] ?? 0), 0)
    const now = Date.now()
    const seconds = (now - lastAt) / 1000

    if (seconds >= 0.5) {
      const sample = (written - lastBytes) / seconds
      // A quarter of the new reading, so the figure settles but still moves.
      rate = rate === 0 ? sample : rate * 0.75 + sample * 0.25
      lastAt = now
      lastBytes = written
    }

    onProgress({
      written,
      total,
      fraction: total > 0 ? Math.min(1, written / total) : 0,
      perSecond: Math.max(0, rate),
      secondsLeft: rate > 0 ? Math.max(0, (total - written) / rate) : null,
    })
  }

  report()

  const saved = await AsyncStorage.getItem(RESUME_KEY)
  const state: ResumeState | null = saved
    ? (JSON.parse(saved) as ResumeState)
    : null

  for (const part of parts) {
    const target = pathOf(model, part)
    const here = await sizeOf(target)
    if (here >= model[part].bytes) continue

    // Carry on from the token when this is the file that stopped.
    const resumeData =
      state && state.modelId === model.id && state.part === part
        ? state.resumeData
        : undefined

    let sinceSave = 0
    const running = FileSystem.createDownloadResumable(
      sourceOf(model, part, onServer),
      target,
      {},
      (progress) => {
        done[part] = progress.totalBytesWritten
        report()
        // The token changes as the download runs. Writing it every tick
        // would hammer storage, so it goes every few megabytes.
        sinceSave += 1
        if (sinceSave % 40 === 0) {
          void saveResume({
            modelId: model.id,
            part,
            resumeData: running.savable().resumeData,
          })
        }
      },
      resumeData,
    )
    task = running
    await saveResume({ modelId: model.id, part, resumeData })

    const result = resumeData
      ? await running.resumeAsync()
      : await running.downloadAsync()
    task = null

    if (stopped) throw new DownloadCancelled()
    if (!result) throw new Error(`The download of the ${part} file stopped.`)
    done[part] = await sizeOf(target)
  }

  await saveResume(null)
  onProgress({
    written: total,
    total,
    fraction: 1,
    perSecond: rate,
    secondsLeft: 0,
  })
}

export async function remove(model: LocalModel): Promise<void> {
  await release()
  for (const part of ['model', 'mmproj'] as const) {
    await FileSystem.deleteAsync(pathOf(model, part), { idempotent: true })
  }
  const pending = await unfinished()
  if (pending?.id === model.id) await saveResume(null)
}

let context: LlamaContext | null = null
let loaded: string | null = null

/** Put the model in memory. The first call after a start takes a moment. */
async function load(model: LocalModel): Promise<LlamaContext> {
  if (context && loaded === model.id) return context
  await release()

  const next = await initLlama({
    model: pathOf(model, 'model'),
    n_ctx: 4096,
    n_gpu_layers: 0,
  })
  await next.initMultimodal({
    path: pathOf(model, 'mmproj'),
    use_gpu: false,
    // A high resolution picture costs tokens and seconds. This bounds both.
    image_max_tokens: model.imageTokens,
  })

  context = next
  loaded = model.id
  return next
}

export async function release(): Promise<void> {
  if (!context) return
  try {
    await context.release()
  } finally {
    context = null
    loaded = null
  }
}

/** What one run cost, so the interface can say it plainly. */
export interface LocalRun {
  items: RecognizedItem[]
  raw: string
  ms: number
}

/** Read the JSON that the model wrote, whatever it wrapped it in. */
function itemsOf(answer: string): RecognizedItem[] {
  const fenced = answer.replace(/```json|```/g, '')
  const start = fenced.search(/[[{]/)
  if (start < 0) return []
  const text = fenced.slice(start)

  for (const end of [text.lastIndexOf(']'), text.lastIndexOf('}')]) {
    if (end < 0) continue
    try {
      const parsed: unknown = JSON.parse(text.slice(0, end + 1))
      const list = Array.isArray(parsed)
        ? parsed
        : ((parsed as { items?: unknown[] }).items ?? [parsed])
      return list
        .filter((entry): entry is Record<string, unknown> => Boolean(entry))
        .map((entry) => ({
          name: String(entry.name ?? '').trim(),
          brand: (entry.brand as string | null) ?? null,
          model: (entry.model as string | null) ?? null,
          serial_number: (entry.serial_number as string | null) ?? null,
          category: (entry.category as string | null) ?? null,
          subcategory: (entry.subcategory as string | null) ?? null,
          condition: (entry.condition as string | null) ?? null,
          estimated_value_aud:
            entry.estimated_value_aud === undefined || entry.estimated_value_aud === null
              ? null
              : String(entry.estimated_value_aud),
          confidence: null,
          region: null,
        }))
        .filter((item) => item.name.length > 0)
    } catch {
      continue
    }
  }
  return []
}

/** Name what is in one photograph, on the phone. */
export async function recognize(
  model: LocalModel,
  imageUri: string,
): Promise<LocalRun> {
  const llama = await load(model)
  const started = Date.now()

  const answer = await llama.completion({
    messages: [
      {
        role: 'user',
        content: [
          { type: 'text', text: PROMPT },
          { type: 'image_url', image_url: { url: imageUri } },
        ],
      },
    ],
    n_predict: 320,
    temperature: 0.1,
    stop: ['</s>', '<|im_end|>', '<end_of_utterance>'],
  })

  return {
    ms: Date.now() - started,
    items: itemsOf(answer.text ?? ''),
    raw: answer.text ?? '',
  }
}
