/**
 * Photograph upload with an instant preview.
 *
 * The preview appears from the local file, so the user sees the picture
 * before the server has resized it.
 */

import { Camera, ImagePlus, Star, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'

import { mediaUrl } from '@/api/client'
import type { ItemPhoto } from '@/api/types'
import { useDeletePhoto, useUploadPhotos } from '@/hooks/useItems'
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
  const fileInput = useRef<HTMLInputElement>(null)
  const cameraInput = useRef<HTMLInputElement>(null)
  const [previews, setPreviews] = useState<string[]>([])
  const [doomed, setDoomed] = useState<string | null>(null)

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
            {photo.is_primary ? (
              <span className="absolute left-1.5 top-1.5 rounded bg-ink-950/70 p-1 text-white">
                <Star className="h-3 w-3 fill-current" />
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
