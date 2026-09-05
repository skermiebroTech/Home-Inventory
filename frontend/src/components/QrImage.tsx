import { QrCode } from 'lucide-react'

import { useBlobUrl } from '@/hooks/useBlobUrl'
import { Spinner } from './ui'

/** One QR code, loaded with the bearer token that the route needs. */
export default function QrImage({
  path,
  alt,
  className,
}: {
  path: string
  alt: string
  className?: string
}) {
  const { url, error } = useBlobUrl(path)

  if (error) {
    return (
      <div className="flex aspect-square w-full items-center justify-center rounded-lg border border-dashed border-ink-300 text-ink-400 dark:border-ink-700">
        <QrCode className="h-6 w-6" />
      </div>
    )
  }
  if (!url) {
    return (
      <div className="flex aspect-square w-full items-center justify-center rounded-lg border border-ink-200 dark:border-ink-800">
        <Spinner />
      </div>
    )
  }
  return <img src={url} alt={alt} className={className} />
}
