/**
 * The add form.
 *
 * The scan tab sends its result here as route parameters, so the quick add
 * flow is: point, shoot, check, save. The save writes to SQLite and queues
 * the change, so it works with no network.
 */

import { useLocalSearchParams, useRouter } from 'expo-router'
import { useState } from 'react'
import { KeyboardAvoidingView, Platform, ScrollView, View } from 'react-native'

import { Body, Button, Caption, Card, Field, Input, Screen } from '@/components/ui'
import { listLocations } from '@/db'
import { useEffect } from 'react'
import type { Location } from '@/api/types'
import { attachPhoto, createItem } from '@/sync/mutations'
import { useSyncStore } from '@/store/sync'
import { radius, spacing, useTheme } from '@/theme'
import { Pressable } from 'react-native'

export default function AddItem() {
  const theme = useTheme()
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
  const photos = (params.photos ?? '').split('|').filter(Boolean)
  const sync = useSyncStore()

  const [name, setName] = useState(params.name ?? '')
  const [brand, setBrand] = useState(params.brand ?? '')
  const [category, setCategory] = useState(params.category ?? '')
  const [value, setValue] = useState(params.value ?? '')
  const [quantity, setQuantity] = useState('1')
  const [notes, setNotes] = useState('')
  const [locationId, setLocationId] = useState<string | null>(null)
  const [locations, setLocations] = useState<Location[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void (async () => setLocations(await listLocations()))()
  }, [])

  const save = async (): Promise<void> => {
    if (!name.trim()) return
    setSaving(true)
    try {
      const item = await createItem({
        name: name.trim(),
        brand: brand.trim() || null,
        model: params.model || null,
        serial_number: params.serial || null,
        category: category.trim() || null,
        current_value: value.trim() || null,
        condition: params.condition || null,
        barcode: params.barcode || null,
        quantity: Number.parseInt(quantity, 10) || 1,
        notes: notes.trim() || null,
        location_id: locationId,
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
            <Field label="Name">
              <Input value={name} onChangeText={setName} autoFocus placeholder="Cordless drill" />
            </Field>
            <Field label="Brand">
              <Input value={brand} onChangeText={setBrand} />
            </Field>
            <Field label="Category">
              <Input value={category} onChangeText={setCategory} placeholder="Tools" />
            </Field>

            <View style={{ flexDirection: 'row', gap: spacing.md }}>
              <View style={{ flex: 1 }}>
                <Field label="Value">
                  <Input value={value} onChangeText={setValue} keyboardType="decimal-pad" />
                </Field>
              </View>
              <View style={{ width: 96 }}>
                <Field label="Quantity">
                  <Input value={quantity} onChangeText={setQuantity} keyboardType="number-pad" />
                </Field>
              </View>
            </View>

            <Field label="Location">
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm }}>
                <Chip
                  label="None"
                  active={locationId === null}
                  onPress={() => setLocationId(null)}
                />
                {locations.map((location) => (
                  <Chip
                    key={location.id}
                    label={location.name}
                    active={locationId === location.id}
                    onPress={() => setLocationId(location.id)}
                  />
                ))}
              </View>
            </Field>

            <Field label="Notes">
              <Input value={notes} onChangeText={setNotes} multiline numberOfLines={3} />
            </Field>
          </Card>

          <Button
            title="Save the item"
            icon="checkmark"
            onPress={() => void save()}
            loading={saving}
            disabled={!name.trim()}
          />
          <Caption>
            The item is saved on the phone at once. The server gets it on the next sync.
          </Caption>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  )
}

function Chip({
  label,
  active,
  onPress,
}: {
  label: string
  active: boolean
  onPress: () => void
}) {
  const theme = useTheme()
  return (
    <Pressable
      onPress={onPress}
      style={{
        paddingHorizontal: 12,
        paddingVertical: 7,
        borderRadius: radius.lg,
        borderWidth: 1,
        borderColor: active ? theme.accent : theme.border,
        backgroundColor: active ? `${theme.accent}22` : 'transparent',
      }}
    >
      <Caption tone={active ? theme.accent : theme.muted}>{label}</Caption>
    </Pressable>
  )
}
