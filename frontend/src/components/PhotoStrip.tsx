/**
 * The photographs of a component or of a cable.
 *
 * Smaller than the item uploader, because these rows need less: a picture,
 * the star that picks the thumbnail, and the bin.
 */

import { ImagePlus, Star, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'

import { mediaUrl } from '@/api/client'
import {
  useDeleteOwnerPhoto,
  usePhotos,
  useSetPrimaryOwnerPhoto,
  useUploadOwnerPhotos,
} from '@/hooks/usePhotos'
import { cx } from '@/lib/format'
import { toastError, toastOk } from '@/store/toast'
import { Button, ConfirmDialog } from './ui'

export default function PhotoStrip({
  owner,
  ownerId,
}: {
  owner: 'components' | 'cables'
  ownerId: string
}) {
  const { data } = usePhotos(owner, ownerId)
  const upload = useUploadOwnerPhotos(owner, ownerId)
  const setPrimary = useSetPrimaryOwnerPhoto(owner, ownerId)
  const remove = useDeleteOwnerPhoto(owner, ownerId)

  const input = useRef<HTMLInputElement>(null)
  const [doomed, setDoomed] = useState<string | null>(null)

  const send = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    try {
      await upload.mutateAsync(Array.from(files))
      toastOk(files.length === 1 ? 'The photograph is saved.' : 'The photographs are saved.')
    } catch (error) {
      toastError(error)
    }
  }

  const rows = data ?? []

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {rows.map((photo) => (
          <figure
            key={photo.id}
            className="group relative h-20 w-20 overflow-hidden rounded-lg border border-ink-200 dark:border-ink-800"
          >
            <img
              src={mediaUrl(photo.thumbnail_path ?? photo.file_path)}
              alt={photo.caption ?? ''}
              loading="lazy"
              className="h-full w-full object-cover"
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
                'absolute left-1 top-1 rounded bg-ink-950/70 p-1 text-white transition-opacity',
                photo.is_primary
                  ? 'opacity-100'
                  : 'opacity-0 group-hover:opacity-100 focus:opacity-100',
              )}
            >
              <Star className={cx('h-3 w-3', photo.is_primary && 'fill-current')} />
            </button>
            <button
              type="button"
              onClick={() => setDoomed(photo.id)}
              aria-label="Delete this photograph"
              className="absolute right-1 top-1 rounded bg-ink-950/70 p-1 text-white opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </figure>
        ))}

        <input
          ref={input}
          type="file"
          accept="image/*"
          multiple
          hidden
          onChange={(event) => void send(event.target.files)}
        />
        <Button
          type="button"
          variant="secondary"
          loading={upload.isPending}
          onClick={() => input.current?.click()}
          icon={<ImagePlus className="h-4 w-4" />}
          className="h-20"
        >
          {rows.length === 0 ? 'Add a photograph' : 'Add'}
        </Button>
      </div>

      {rows.length > 1 ? (
        <p className="mt-1 text-xs text-ink-500">
          The star picks the picture that the list shows.
        </p>
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
