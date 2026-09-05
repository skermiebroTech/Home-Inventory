/** One item: the details, the photographs, lending, and the service log. */

import { Ionicons } from '@expo/vector-icons'
import { Image } from 'expo-image'
import * as ImagePicker from 'expo-image-picker'
import { useLocalSearchParams, useRouter } from 'expo-router'
import { useCallback, useEffect, useState } from 'react'
import { Alert, ScrollView, View } from 'react-native'
import { useFocusEffect } from 'expo-router'

import { mediaUrl } from '@/api/client'
import type { FittedComponent, ItemPhoto, MaintenanceLog } from '@/api/types'
import { Badge, Body, Button, Caption, Card, Field, Input, Loading, Screen, Title } from '@/components/ui'
import {
  getItem,
  getItemPhotos,
  listItemComponents,
  listMaintenance,
  type LocalItem,
} from '@/db'
import { daysUntil, formatDate, formatMoney } from '@/lib/format'
import { NfcUnavailableError, scanAndRegister } from '@/lib/nfc'
import {
  addMaintenance,
  attachPhoto,
  deleteItem,
  lendItem,
  returnItem,
} from '@/sync/mutations'
import { useSyncStore } from '@/store/sync'
import { radius, spacing, useTheme } from '@/theme'

export default function ItemScreen() {
  const theme = useTheme()
  const router = useRouter()
  const { id } = useLocalSearchParams<{ id: string }>()
  const sync = useSyncStore()

  const [item, setItem] = useState<LocalItem | null>(null)
  const [photos, setPhotos] = useState<ItemPhoto[]>([])
  const [logs, setLogs] = useState<MaintenanceLog[]>([])
  const [parts, setParts] = useState<FittedComponent[]>([])
  const [borrower, setBorrower] = useState('')
  const [showLend, setShowLend] = useState(false)
  const [work, setWork] = useState('')
  const [showWork, setShowWork] = useState(false)

  const load = useCallback(async () => {
    if (!id) return
    setItem(await getItem(id))
    setPhotos(await getItemPhotos(id))
    setLogs(await listMaintenance(id))
    setParts(await listItemComponents(id))
  }, [id])

  useFocusEffect(
    useCallback(() => {
      void load()
    }, [load]),
  )

  // A sync that finishes while this screen is open changes the row under it,
  // so the screen reads it again.
  useEffect(() => {
    void load()
  }, [load, sync.lastSync])

  if (!item) return <Loading label="Reading the item" />

  const addPhoto = async (): Promise<void> => {
    // Several pictures at once: the item, its label, and its box.
    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 })
    if (result.canceled || !result.assets[0]) return
    await attachPhoto(item.id, result.assets[0].uri)
    await load()
    await sync.refreshCounts()
    Alert.alert(
      'The photograph is queued',
      'It goes up on the next sync over WiFi. The server reads any text on it.',
    )
  }

  const addFromLibrary = async (): Promise<void> => {
    const result = await ImagePicker.launchImageLibraryAsync({
      quality: 0.7,
      allowsMultipleSelection: true,
    })
    if (result.canceled) return
    for (const asset of result.assets) await attachPhoto(item.id, asset.uri)
    await load()
    await sync.refreshCounts()
    Alert.alert(
      'Queued',
      `${result.assets.length} photographs go up on the next sync.`,
    )
  }

  return (
    <Screen edges={['bottom']}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}>
        <View>
          <Title>{item.name}</Title>
          <View style={{ flexDirection: 'row', gap: spacing.sm, marginTop: 6 }}>
            {item.pending ? <Badge text="waiting to send" tone={theme.warn} /> : null}
            {item.is_lent ? <Badge text={`with ${item.lent_to}`} tone={theme.warn} /> : null}
          </View>
        </View>

        {photos.length > 0 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -4 }}>
            {photos.map((photo) => (
              <Image
                key={photo.id}
                source={{ uri: mediaUrl(photo.file_path) }}
                style={{ width: 150, height: 150, borderRadius: radius.md, margin: 4 }}
                contentFit="cover"
                transition={150}
              />
            ))}
          </ScrollView>
        ) : null}

        <View style={{ flexDirection: 'row', gap: spacing.sm }}>
          <Button
            title="Edit"
            icon="create"
            onPress={() => router.push(`/items/${item.id}/edit`)}
            style={{ flex: 1 }}
          />
          {item.is_lent ? (
            <Button
              title="Returned"
              icon="arrow-undo"
              variant="secondary"
              style={{ flex: 1 }}
              onPress={async () => {
                await returnItem(item.id)
                await load()
                await sync.refreshCounts()
              }}
            />
          ) : (
            <Button
              title="Lend"
              icon="hand-left"
              variant="secondary"
              style={{ flex: 1 }}
              onPress={() => setShowLend((open) => !open)}
            />
          )}
        </View>

        <View style={{ flexDirection: 'row', gap: spacing.sm }}>
          <Button
            title="Photograph"
            icon="camera"
            variant="secondary"
            onPress={() => void addPhoto()}
            style={{ flex: 1 }}
          />
          <Button
            title="Library"
            icon="images"
            variant="secondary"
            onPress={() => void addFromLibrary()}
            style={{ flex: 1 }}
          />
        </View>

        {showLend ? (
          <Card>
            <Field label="Who has it">
              <Input value={borrower} onChangeText={setBorrower} placeholder="Dave next door" autoFocus />
            </Field>
            <Button
              title="Lend it"
              disabled={!borrower.trim()}
              onPress={async () => {
                await lendItem(item.id, borrower.trim())
                setShowLend(false)
                setBorrower('')
                await load()
                await sync.refreshCounts()
              }}
            />
          </Card>
        ) : null}

        {photos.some((photo) => photo.ocr_text) ? (
          <Card>
            <Body weight="600">Text on the photographs</Body>
            <Caption>
              The server read this with OCR. It often holds the model and the
              serial number.
            </Caption>
            <View style={{ marginTop: spacing.sm, gap: spacing.sm }}>
              {photos
                .filter((photo) => photo.ocr_text)
                .map((photo, index) => (
                  <View key={photo.id}>
                    <Caption>Photograph {index + 1}</Caption>
                    <Body>{photo.ocr_text}</Body>
                  </View>
                ))}
            </View>
          </Card>
        ) : null}

        <Card>
          <Detail label="Value" value={formatMoney(item.current_value ?? item.purchase_price)} />
          <Detail label="Quantity" value={String(item.quantity)} />
          <Detail label="Category" value={item.category} />
          <Detail label="Brand and model" value={[item.brand, item.model].filter(Boolean).join(' ')} />
          <Detail label="Serial number" value={item.serial_number} />
          <Detail label="Barcode" value={item.barcode} />
          <Detail label="Condition" value={item.condition} />
          <Detail label="Bought" value={item.purchase_date ? formatDate(item.purchase_date) : null} />
          <Detail
            label="Warranty ends"
            value={
              item.warranty_expires
                ? `${formatDate(item.warranty_expires)} (${daysUntil(item.warranty_expires)} days)`
                : null
            }
          />
          <Detail label="Notes" value={item.notes} />
        </Card>

        {parts.length > 0 ? (
          <Card>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <Body weight="600">Components</Body>
              <View style={{ flex: 1 }} />
              <Caption>
                {formatMoney(parts.reduce((sum, part) => sum + part.line_total, 0))}
              </Caption>
            </View>

            <View style={{ marginTop: spacing.sm, gap: spacing.md }}>
              {parts.map((part) => (
                <View key={part.id}>
                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <Body weight="500">
                      {part.quantity > 1 ? `${part.quantity}x ` : ''}
                      {part.name}
                    </Body>
                    <View style={{ flex: 1 }} />
                    <Body>{formatMoney(part.line_total)}</Body>
                  </View>
                  <Caption>
                    {[part.brand, part.model_number].filter(Boolean).join(' · ') ||
                      'No brand'}
                    {part.serial_number ? ` · serial ${part.serial_number}` : ''}
                    {part.price ? ' · own price' : ' · default price'}
                  </Caption>
                  {part.notes ? <Caption>{part.notes}</Caption> : null}
                </View>
              ))}
            </View>
          </Card>
        ) : null}

        <Card style={{ padding: 0 }}>
          <View style={{ padding: spacing.lg, flexDirection: 'row', alignItems: 'center' }}>
            <Body weight="600">Service history</Body>
            <View style={{ flex: 1 }} />
            <Ionicons
              name={showWork ? 'close' : 'add'}
              size={20}
              color={theme.accent}
              onPress={() => setShowWork((open) => !open)}
            />
          </View>

          {showWork ? (
            <View style={{ paddingHorizontal: spacing.lg, paddingBottom: spacing.lg }}>
              <Field label="What was done">
                <Input value={work} onChangeText={setWork} placeholder="Changed the oil" autoFocus />
              </Field>
              <Button
                title="Record it"
                disabled={!work.trim()}
                onPress={async () => {
                  await addMaintenance(item.id, { description: work.trim() })
                  setWork('')
                  setShowWork(false)
                  await load()
                  await sync.refreshCounts()
                }}
              />
            </View>
          ) : null}

          {logs.length === 0 ? (
            <View style={{ paddingHorizontal: spacing.lg, paddingBottom: spacing.lg }}>
              <Caption>No work recorded.</Caption>
            </View>
          ) : (
            logs.map((log) => (
              <View
                key={log.id}
                style={{ paddingHorizontal: spacing.lg, paddingBottom: spacing.md }}
              >
                <Body>{log.description}</Body>
                <Caption>
                  {formatDate(log.date_performed)}
                  {log.next_due_date ? ` · next ${formatDate(log.next_due_date)}` : ''}
                </Caption>
              </View>
            ))
          )}
        </Card>

        <Button
          title="Bind an NFC tag"
          variant="secondary"
          icon="radio"
          onPress={async () => {
            try {
              const uid = await scanAndRegister({ itemId: item.id, label: item.name })
              Alert.alert('The tag is bound', `Tag ${uid} now opens ${item.name}.`)
            } catch (error) {
              Alert.alert(
                error instanceof NfcUnavailableError ? 'No NFC here' : 'That did not work',
                error instanceof Error ? error.message : 'The tag did not read.',
              )
            }
          }}
        />

        <Button
          title="Delete this item"
          variant="danger"
          icon="trash"
          onPress={() => {
            Alert.alert('Delete this item?', 'The server learns about it on the next sync.', [
              { text: 'Cancel', style: 'cancel' },
              {
                text: 'Delete',
                style: 'destructive',
                onPress: async () => {
                  await deleteItem(item.id)
                  await sync.refreshCounts()
                  router.back()
                },
              },
            ])
          }}
        />
      </ScrollView>
    </Screen>
  )
}

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5 }}>
      <Caption>{label}</Caption>
      <Body>{value}</Body>
    </View>
  )
}
