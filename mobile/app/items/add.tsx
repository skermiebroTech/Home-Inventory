/**
 * The add form.
 *
 * The scan tab sends its result here as route parameters, so the quick add
 * flow is: point, shoot, check, save. The save writes to SQLite and queues
 * the change, so it works with no network.
 */

import { useLocalSearchParams, useRouter } from 'expo-router'
import { useState } from 'react'
import { KeyboardAvoidingView, Platform, ScrollView } from 'react-native'

import ItemFields, {
  emptyValues,
  toDraft,
  type ItemFormValues,
} from '@/components/ItemFields'
import { Body, Button, Caption, Card, Screen } from '@/components/ui'
import { attachPhoto, createItem } from '@/sync/mutations'
import { useSyncStore } from '@/store/sync'
import { spacing }  from '@/theme'

export default function AddItem() {
  const router = useRouter()
  const params = useLocalSearchParams<{
    name?: string
    brand?: string
    model?: string
    serial?: string
    category?: string
    condition?: string
    value?: string
    barcode?: string
    /** The scan joins the photograph paths with a vertical bar. */
    photos?: string
  }>()
  const sync = useSyncStore()
  const photos = (params.photos ?? '').split('|').filter(Boolean)

  const [values, setValues] = useState<ItemFormValues>(() =>
    emptyValues({
      name: params.name ?? '',
      brand: params.brand ?? '',
      model: params.model ?? '',
      serial_number: params.serial ?? '',
      category: params.category ?? '',
      current_value: params.value ?? '',
      condition: params.condition ?? '',
    }),
  )
  const [saving, setSaving] = useState(false)

  const save = async (): Promise<void> => {
    if (!values.name.trim()) return
    setSaving(true)
    try {
      const item = await createItem({
        ...toDraft(values),
        barcode: params.barcode || null,
      })
      for (const uri of photos) await attachPhoto(item.id, uri)

      await sync.refreshCounts()
      void sync.run()
      router.replace(`/items/${item.id}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Screen edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}>
          {photos.length > 0 ? (
            <Card>
              <Body weight="600">
                {photos.length === 1
                  ? 'The photograph is attached'
                  : `${photos.length} photographs are attached`}
              </Body>
              <Caption>
                They go up on the next sync. The default setting waits for WiFi.
              </Caption>
            </Card>
          ) : null}

          {params.serial || params.model ? (
            <Card>
              <Body weight="600">Read from the label</Body>
              {params.model ? <Caption>Model: {params.model}</Caption> : null}
              {params.serial ? <Caption>Serial: {params.serial}</Caption> : null}
              <Caption>Check these before you save.</Caption>
            </Card>
          ) : null}

          <Card>
            <ItemFields values={values} onChange={setValues} autoFocus />
          </Card>

          <Button
            title="Save the item"
            icon="checkmark"
            onPress={() => void save()}
            loading={saving}
            disabled={!values.name.trim()}
          />
          <Caption>
            The item is saved on the phone at once. The server gets it on the
            next sync.
          </Caption>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  )
}
