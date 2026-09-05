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

import * as FileSystem from 'expo-file-system'
import { initLlama, type LlamaContext } from 'llama.rn'

import type { RecognizedItem } from '@/api/types'

/** Where the weights live. The cache directory would be swept by Android. */
const HOME = `${FileSystem.documentDirectory}models/`

export interface LocalModel {
  id: string
  name: string
  /** What a person sees before they spend the download. */
  size: string
  note: string
  /** The weights, and the part that reads a picture. */
  model: string
  mmproj: string
  /** Tokens that one picture may cost. It bounds the time per photograph. */
  imageTokens: number
}

export const MODELS: LocalModel[] = [
  {
    id: 'smolvlm2-2.2b',
    name: 'SmolVLM2 2.2B',
    size: '1.7 GB',
    note: 'Slower, and it names things better.',
    model:
      'https://huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF/resolve/main/SmolVLM2-2.2B-Instruct-Q4_K_M.gguf',
    mmproj:
      'https://huggingface.co/ggml-org/SmolVLM2-2.2B-Instruct-GGUF/resolve/main/mmproj-SmolVLM2-2.2B-Instruct-Q8_0.gguf',
    imageTokens: 900,
  },
  {
    id: 'smolvlm2-500m',
    name: 'SmolVLM2 500M',
    size: '546 MB',
    note: 'Quick, and it misses detail.',
    model:
      'https://huggingface.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main/SmolVLM2-500M-Video-Instruct-Q8_0.gguf',
    mmproj:
      'https://huggingface.co/ggml-org/SmolVLM2-500M-Video-Instruct-GGUF/resolve/main/mmproj-SmolVLM2-500M-Video-Instruct-Q8_0.gguf',
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

/**
 * Fetch the weights.
 *
 * `onProgress` reports a number between 0 and 1 across both files together,
 * because a person watching a bar does not care that there are two.
 */
export async function download(
  model: LocalModel,
  onProgress: (fraction: number) => void,
): Promise<void> {
  await FileSystem.makeDirectoryAsync(HOME, { intermediates: true }).catch(
    () => undefined,
  )

  const parts: Array<'model' | 'mmproj'> = ['model', 'mmproj']
  const totals: Record<string, number> = {}
  const done: Record<string, number> = {}

  for (const part of parts) {
    const target = pathOf(model, part)
    if ((await sizeOf(target)) > 0) continue

    const task = FileSystem.createDownloadResumable(
      model[part],
      target,
      {},
      (state) => {
        totals[part] = state.totalBytesExpectedToWrite
        done[part] = state.totalBytesWritten
        const whole = parts.reduce((sum, key) => sum + (totals[key] ?? 0), 0)
        const so_far = parts.reduce((sum, key) => sum + (done[key] ?? 0), 0)
        if (whole > 0) onProgress(Math.min(1, so_far / whole))
      },
    )
    await task.downloadAsync()
  }
  onProgress(1)
}

export async function remove(model: LocalModel): Promise<void> {
  await release()
  for (const part of ['model', 'mmproj'] as const) {
    await FileSystem.deleteAsync(pathOf(model, part), { idempotent: true })
  }
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
