/**
 * Edit one item.
 *
 * The change lands in the local database at once and joins the outbox, so a
 * correction made with no signal reaches the server on the next sync. The
 * server keeps the last write, and the version it holds decides a conflict.
 */

import { useLocalSearchParams, useRouter } from 'expo-router'
import { useEffect, useState } from 'react'
import { Alert, KeyboardAvoidingView, Platform, ScrollView, View } from 'react-native'

import ItemFields, {
  emptyValues,
  toDraft,
  type ItemFormValues,
} from '@/components/ItemFields'
import { Body, Button, Caption, Card, Loading, Screen } from '@/components/ui'
import { getItem, type LocalItem } from '@/db'
import { updateItem } from '@/sync/mutations'
import { useSyncStore } from '@/store/sync'
import { spacing } from '@/theme'

function valuesOf(item: LocalItem): ItemFormValues {
  return emptyValues({
    name: item.name,
    brand: item.brand ?? '',
    model: item.model ?? '',
    serial_number: item.serial_number ?? '',
    category: item.category ?? '',
    current_value: item.current_value ?? item.purchase_price ?? '',
    quantity: String(item.quantity ?? 1),
    condition: item.condition ?? '',
    location_id: item.location_id,
    purchase_date: item.purchase_date ?? '',
    warranty_expires: item.warranty_expires ?? '',
    notes: item.notes ?? '',
    owner: item.owner ?? '',
  })
}

export default function EditItem() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const router = useRouter()
  const sync = useSyncStore()

  const [values, setValues] = useState<ItemFormValues | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void (async () => {
      if (!id) return
      const item = await getItem(id)
      setValues(item ? valuesOf(item) : null)
    })()
  }, [id])

  if (!values) return <Loading label="Reading the item" />

  const save = async (): Promise<void> => {
    if (!id || !values.name.trim()) return
    setSaving(true)
    try {
      await updateItem(id, toDraft(values))
      await sync.refreshCounts()
      // The push goes out now if there is a signal, and waits if there is not.
      void sync.run()
      router.back()
    } catch (error) {
      Alert.alert(
        'That did not save',
        error instanceof Error ? error.message : 'Unknown failure.',
      )
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
          <Card>
            <ItemFields values={values} onChange={setValues} />
          </Card>

          <Button
            title="Save the changes"
            icon="checkmark"
            onPress={() => void save()}
            loading={saving}
            disabled={!values.name.trim()}
          />
          <Button
            title="Cancel"
            variant="secondary"
            onPress={() => router.back()}
          />

          <View>
            <Caption>
              The change is saved on the phone at once. The server gets it on
              the next sync, and it wins unless the server holds a newer copy.
            </Caption>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  )
}
