/**
 * Photograph upload with an instant preview.
 *
 * The preview appears from the local file, so the user sees the picture
 * before the server has resized it.
 */

import { Camera, ImagePlus, ScanText, Star, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'

import { mediaUrl } from '@/api/client'
import type { ItemPhoto } from '@/api/types'
import { useDeletePhoto, useUploadPhotos } from '@/hooks/useItems'
import { useSetPrimaryItemPhoto } from '@/hooks/usePhotos'
import { cx } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'
import { Button, ConfirmDialog } from './ui'

export default function PhotoUploader({
  itemId,
  photos,
}: {
  itemId: string
  photos: ItemPhoto[]
}) {
  const upload = useUploadPhotos(itemId)
  const remove = useDeletePhoto(itemId)
  const setPrimary = useSetPrimaryItemPhoto(itemId)
  const fileInput = useRef<HTMLInputElement>(null)
  const cameraInput = useRef<HTMLInputElement>(null)
  const [previews, setPreviews] = useState<string[]>([])
  const [doomed, setDoomed] = useState<string | null>(null)
  const withText = photos.filter((photo) => photo.ocr_text)

  const send = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const list = Array.from(files)
    setPreviews(list.map((file) => URL.createObjectURL(file)))
    try {
      await upload.mutateAsync(list)
      toastOk(list.length === 1 ? 'The photograph is saved.' : 'The photographs are saved.')
    } catch (error) {
      toastError(error)
    } finally {
      previews.forEach(URL.revokeObjectURL)
      setPreviews([])
    }
  }

  return (
    <div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {photos.map((photo) => (
          <figure key={photo.id} className="group relative overflow-hidden rounded-lg border border-ink-200 dark:border-ink-800">
            <img
              src={mediaUrl(photo.file_path)}
              alt=""
              loading="lazy"
              className="aspect-square w-full object-cover"
            />
            <button
              type="button"
              onClick={async () => {
                if (photo.is_primary) return
                try {
                  await setPrimary.mutateAsync(photo.id)
                  toastOk('That photograph is now the thumbnail.')
                } catch (error) {
                  toastError(error)
                }
              }}
              title={photo.is_primary ? 'This is the thumbnail' : 'Use as the thumbnail'}
              aria-label={
                photo.is_primary ? 'This is the thumbnail' : 'Use as the thumbnail'
              }
              className={cx(
                'absolute left-1.5 top-1.5 rounded bg-ink-950/70 p-1 text-white transition-opacity',
                photo.is_primary
                  ? 'opacity-100'
                  : 'opacity-0 group-hover:opacity-100 focus:opacity-100',
              )}
            >
              <Star className={cx('h-3 w-3', photo.is_primary && 'fill-current')} />
            </button>
            {photo.ocr_text ? (
              <span
                title="The server read text on this photograph"
                className="absolute bottom-1.5 left-1.5 rounded bg-ink-950/70 p-1 text-white"
              >
                <ScanText className="h-3 w-3" />
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => setDoomed(photo.id)}
              aria-label="Delete this photograph"
              className="absolute right-1.5 top-1.5 rounded bg-ink-950/70 p-1 text-white opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </figure>
        ))}

        {previews.map((url) => (
          <div key={url} className="relative overflow-hidden rounded-lg border border-dashed border-accent-400">
            <img src={url} alt="" className="aspect-square w-full object-cover opacity-60" />
            <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-accent-700">
              Saving
            </span>
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          multiple
          hidden
          onChange={(event) => void send(event.target.files)}
        />
        <input
          ref={cameraInput}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(event) => void send(event.target.files)}
        />
        <Button
          type="button"
          variant="secondary"
          loading={upload.isPending}
          onClick={() => fileInput.current?.click()}
          icon={<ImagePlus className="h-4 w-4" />}
        >
          Add photographs
        </Button>
        <p className="w-full text-xs text-ink-500">
          Photograph the item from several sides. The server reads any text it
          finds, so a rating plate gives the model and the serial number.
        </p>
        <Button
          type="button"
          variant="secondary"
          className="sm:hidden"
          onClick={() => cameraInput.current?.click()}
          icon={<Camera className="h-4 w-4" />}
        >
          Camera
        </Button>
      </div>

      {withText.length > 0 ? (
        <details className="mt-3 rounded-lg border border-ink-200 p-3 text-sm dark:border-ink-800">
          <summary className="cursor-pointer font-medium">
            Text on {withText.length}{' '}
            {withText.length === 1 ? 'photograph' : 'photographs'}
          </summary>
          <p className="mt-1 text-xs text-ink-500">
            The server read this with OCR. Copy a model number or a serial
            number straight into the item.
          </p>
          <div className="mt-2 space-y-2">
            {withText.map((photo, index) => (
              <div key={photo.id}>
                <p className="text-xs font-medium text-ink-500">
                  Photograph {index + 1}
                </p>
                <pre className="mt-0.5 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-ink-100 p-2 text-xs dark:bg-ink-950">
                  {photo.ocr_text}
                </pre>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <ConfirmDialog
        open={doomed !== null}
        title="Delete this photograph?"
        message="The original and every thumbnail go away. This cannot be undone."
        loading={remove.isPending}
        onCancel={() => setDoomed(null)}
        onConfirm={async () => {
          if (!doomed) return
          try {
            await remove.mutateAsync(doomed)
            toastOk('The photograph is deleted.')
          } catch (error) {
            toastError(error)
          } finally {
            setDoomed(null)
          }
        }}
      />
    </div>
  )
}
