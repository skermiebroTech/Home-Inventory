/**
 * Add one item, or add many after a bulk scan.
 *
 * Three ways in: type it, photograph it and let the model fill the form, or
 * read a barcode and let the product database fill it.
 */

import { ArrowLeft, Boxes } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import type { RecognizedItem } from '@/api/types'
import { AiPhotoButton, BarcodeButton, SuggestionList } from '@/components/AiAssist'
import ItemForm, { emptyItem, type ItemFormValues } from '@/components/ItemForm'
import { Button, Card, Modal, PageHeader } from '@/components/ui'
import { items as itemsApi } from '@/api/endpoints'
import { useBulkCreateItems, useCreateItem } from '@/hooks/useItems'
import { toastError, toastOk } from '@/store/toast'

function fromSuggestion(entry: RecognizedItem): Partial<ItemFormValues> {
  return {
    name: entry.name,
    brand: entry.brand,
    model: entry.model,
    serial_number: entry.serial_number,
    category: entry.category,
    subcategory: entry.subcategory,
    condition: entry.condition,
    current_value: entry.estimated_value_aud,
  }
}

export default function AddItem() {
  const navigate = useNavigate()
  const create = useCreateItem()
  const bulkCreate = useBulkCreateItems()
  const [values, setValues] = useState<ItemFormValues>(emptyItem())
  // Every photograph that the scan used is attached to the item on save.
  const [photos, setPhotos] = useState<File[]>([])
  const [readText, setReadText] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<RecognizedItem[] | null>(null)
  const [chosen, setChosen] = useState<number[]>([])
  const [saving, setSaving] = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      const item = await create.mutateAsync({ ...values })
      // The photographs that the model read become the item photographs.
      if (photos.length > 0) await itemsApi.uploadPhotos(item.id, photos)
      toastOk('The item is saved.')
      navigate(`/items/${item.id}`)
    } catch (error) {
      toastError(error)
    } finally {
      setSaving(false)
    }
  }

  const takeSuggestions = (
    entries: RecognizedItem[],
    files: File[],
    text: string | null,
  ) => {
    setPhotos(files)
    setReadText(text)
    if (entries.length === 0) {
      toastError(new Error('The model found no item in those photographs.'))
      return
    }
    if (entries.length === 1 && entries[0]) {
      setValues({ ...values, ...fromSuggestion(entries[0]) } as ItemFormValues)
      toastOk('The form is filled. Check it before you save.')
      return
    }
    setSuggestions(entries)
    setChosen(entries.map((_, index) => index))
  }

  const saveMany = async () => {
    if (!suggestions) return
    const bodies = chosen
      .map((index) => suggestions[index])
      .filter((entry): entry is RecognizedItem => Boolean(entry))
      .map((entry) => ({ ...emptyItem(fromSuggestion(entry)) }))
    try {
      const created = await bulkCreate.mutateAsync(bodies)
      toastOk(`${created.length} items are saved.`)
      setSuggestions(null)
      navigate('/items')
    } catch (error) {
      toastError(error)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to="/items"
        className="mb-3 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-200"
      >
        <ArrowLeft className="h-4 w-4" /> Items
      </Link>

      <PageHeader title="Add an item" subtitle="Type it, photograph it, or read its barcode." />

      <Card>
        <ItemForm
          values={values}
          onChange={setValues}
          onSubmit={() => void save()}
          onCancel={() => navigate('/items')}
          saving={saving || create.isPending}
          submitLabel="Save the item"
          extra={
            <div className="mb-4 space-y-2 rounded-lg border border-dashed border-ink-300 p-3 dark:border-ink-700">
              <div className="flex flex-wrap gap-2">
              <AiPhotoButton
                onResult={takeSuggestions}
                label="Photograph one item"
              />
              <AiPhotoButton
                mode="bulk"
                onResult={takeSuggestions}
                label="Photograph a shelf"
              />
              <BarcodeButton
                onProduct={(product) =>
                  setValues({
                    ...values,
                    name: product.name ?? values.name,
                    brand: product.brand,
                    category: product.category,
                    description: product.description,
                    barcode: product.barcode,
                  })
                }
              />
              </div>

              <p className="text-xs text-ink-500">
                Choose several photographs at once. A picture of the rating
                plate or the box gives the model number and the serial number.
              </p>

              {photos.length > 0 ? (
                <p className="text-xs text-accent-600 dark:text-accent-400">
                  {photos.length}{' '}
                  {photos.length === 1 ? 'photograph is' : 'photographs are'}{' '}
                  attached to this item.
                </p>
              ) : null}

              {readText ? (
                <details className="text-xs text-ink-500">
                  <summary className="cursor-pointer">
                    The text that the server read
                  </summary>
                  <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap">
                    {readText}
                  </pre>
                </details>
              ) : null}
            </div>
          }
        />
      </Card>

      <Modal
        open={suggestions !== null}
        wide
        title={`The model found ${suggestions?.length ?? 0} items`}
        onClose={() => setSuggestions(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setSuggestions(null)}>
              Cancel
            </Button>
            <Button onClick={() => void saveMany()} loading={bulkCreate.isPending}>
              Save {chosen.length} items
            </Button>
          </>
        }
      >
        <p className="mb-3 flex items-center gap-2 text-sm text-ink-500">
          <Boxes className="h-4 w-4" /> Remove anything the model got wrong.
        </p>
        {suggestions ? (
          <SuggestionList
            suggestions={suggestions}
            selected={chosen}
            onToggle={(index) =>
              setChosen(
                chosen.includes(index)
                  ? chosen.filter((entry) => entry !== index)
                  : [...chosen, index],
              )
            }
          />
        ) : null}
      </Modal>
    </div>
  )
}
